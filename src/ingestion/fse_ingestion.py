import hashlib
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion.fse_edit_metadata import FSEMetadataExtractor
from utils.config_loader import load_config
from utils.ollama_api import get_ollama_api
from core_rag.ingestion import UnifiedIngestion
from core_rag.ingestion.content_extract import extract_content
from core_rag.ingestion.chunking import AdvancedChunker
from core_rag.ingestion.json_extract import JSONContentExtractor
from core_rag.utils.docstore import get_docstore
from core_rag.utils.doc_id import generate_doc_id, get_normalized_path
from core_rag.utils.text_preprocessing import preprocess_for_embedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


class FSEIngestion(UnifiedIngestion):

    def __init__(self):
        self.config = load_config()
        self.client = QdrantClient(
            host=self.config['qdrant']['host'],
            port=self.config['qdrant']['port'],
            timeout=self.config['qdrant']['timeout']
        )
        self.embedding_model = self.config['embedding']['model']
        self.chunker = AdvancedChunker(self.config.get('chunker', {}))
        self.ollama_api = get_ollama_api()
        self.docstore = get_docstore()
        self.json_extractor = JSONContentExtractor(self.config)
        self.metadata_extractor = FSEMetadataExtractor()
        self._ensure_collections_exist()
        self._load_section_patterns()

    # --- helpers ---

    def _get_embedding(self, text: str, task_type: str = 'document') -> List[float]:
        try:
            processed = preprocess_for_embedding([text], task_type, self.config.get('embedding', {}))[0]
            embedding = self.ollama_api.get_embeddings(model=self.embedding_model, prompt=processed)
            return embedding if embedding is not None else []
        except Exception as e:
            print(f"Error getting embedding: {e}")
            return []

    def _generate_chunk_id(self, doc_id: str, chunk_index: int) -> str:
        return hashlib.sha256(f"{doc_id}:chunk:{chunk_index}".encode()).hexdigest()[:32]

    def _get_collection_for_doc_type(self, doc_type: str) -> str:
        mapping = self.config.get('domain', {}).get('document_type_mapping', {})
        return mapping.get(doc_type, list(self.config['qdrant']['collections'].values())[0])

    # --- collection management ---

    def _ensure_collections_exist(self):
        dimension = self.config.get('embedding', {}).get('dimension')
        for collection_name in self.config['qdrant']['collections'].values():
            needs_create = False
            try:
                info = self.client.get_collection(collection_name)
                existing_dim = info.config.params.vectors.size
                if dimension and existing_dim != dimension:
                    print(f"Collection '{collection_name}' has wrong dimension ({existing_dim} vs {dimension}), recreating...")
                    self.client.delete_collection(collection_name)
                    needs_create = True
                else:
                    print(f"Collection '{collection_name}' already exists (dim={existing_dim})")
            except Exception:
                needs_create = True

            if needs_create:
                if dimension is None:
                    test = self._get_embedding("test")
                    dimension = len(test) if test else 4096
                    print(f"Detected vector size {dimension} from test embedding")
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=dimension, distance=Distance.COSINE)
                )
                print(f"Created collection '{collection_name}' with vector size {dimension}")

    # --- section detection ---

    def _load_section_patterns(self):
        section_config = self.config.get('ingestion', {}).get('section_detection', {})
        self.section_detection_enabled = section_config.get('enabled', True)
        self.default_section = section_config.get('default_section', 'general')
        patterns = section_config.get('patterns', [])
        if patterns:
            self.section_patterns = [
                (re.compile(p['pattern'], re.IGNORECASE), p['section'])
                for p in patterns
            ]
        else:
            self.section_patterns = self._get_default_section_patterns()

    def _get_default_section_patterns(self) -> List[Tuple[re.Pattern, str]]:
        return [
            (re.compile(r'grand challenges initiative', re.IGNORECASE), 'grand_challenges'),
            (re.compile(r'lower-division (?:core )?requirements', re.IGNORECASE), 'lower_division'),
            (re.compile(r'upper-division requirements', re.IGNORECASE), 'upper_division'),
            (re.compile(r'electives \(\d+ credits\)', re.IGNORECASE), 'electives'),
            (re.compile(r'professional portfolio', re.IGNORECASE), 'portfolio'),
            (re.compile(r'colloquium requirement', re.IGNORECASE), 'colloquium'),
            (re.compile(r'total credits', re.IGNORECASE), 'summary'),
        ]

    def _find_section_boundaries(self, text: str) -> List[Tuple[int, str]]:
        boundaries = [(0, self.default_section)]
        for pattern, section_name in self.section_patterns:
            for match in pattern.finditer(text):
                boundaries.append((match.start(), section_name))
        boundaries.sort(key=lambda x: x[0])
        return boundaries

    def _get_section_for_position(self, position: int, boundaries: List[Tuple[int, str]]) -> str:
        current_section = self.default_section
        for boundary_pos, section_name in boundaries:
            if boundary_pos <= position:
                current_section = section_name
            else:
                break
        return current_section

    def _find_chunk_position(self, chunk_text: str, full_text: str, start_from: int = 0) -> int:
        chunk_start = chunk_text[:100].strip()
        pos = full_text.find(chunk_start, start_from)
        if pos == -1:
            chunk_start = chunk_text[:50].strip()
            pos = full_text.find(chunk_start, start_from)
        return pos if pos != -1 else start_from

    # --- ingestion ---

    def ingest_pdf_file(self, file_path: str) -> bool:
        try:
            print(f"Ingesting PDF: {file_path}")
            text, tika_metadata = extract_content(file_path)
            if not text or len(text.strip()) < 10:
                print(f"  Warning: No content extracted from {file_path}")
                return False

            file_metadata = self.metadata_extractor.extract_metadata_from_path(file_path)
            combined_metadata = {**tika_metadata, **file_metadata}
            collection_name = self._get_collection_for_doc_type(file_metadata['DocumentType'])

            doc_id = generate_doc_id(file_path)
            source_path = get_normalized_path(file_path)
            last_modified = datetime.fromtimestamp(os.stat(file_path).st_mtime).isoformat()
            self.docstore.put(doc_id, text, {
                'source_path': source_path,
                'title': file_metadata.get('title', Path(file_path).stem),
                'collection_name': collection_name,
                'last_modified': last_modified,
                'content_type': 'pdf',
            })

            combined_metadata['doc_id'] = doc_id
            combined_metadata['source_path'] = source_path

            section_boundaries = []
            if self.section_detection_enabled:
                section_boundaries = self._find_section_boundaries(text)
                print(f"  Found {len(section_boundaries)} section boundaries")

            chunk_data = self.chunker.chunk_text(text, combined_metadata)
            points = []
            last_position = 0

            for i, (chunk_text, chunk_metadata) in enumerate(chunk_data):
                embedding = self._get_embedding(chunk_text)
                if not embedding:
                    continue
                if self.section_detection_enabled and section_boundaries:
                    chunk_position = self._find_chunk_position(chunk_text, text, last_position)
                    chunk_metadata['section'] = self._get_section_for_position(chunk_position, section_boundaries)
                    last_position = chunk_position
                chunk_metadata['chunk_text'] = chunk_text
                chunk_metadata['chunk_index'] = i
                chunk_metadata['total_chunks'] = len(chunk_data)
                points.append(PointStruct(
                    id=self._generate_chunk_id(doc_id, i),
                    vector=embedding,
                    payload=chunk_metadata,
                ))

            if points:
                self.client.upsert(collection_name=collection_name, points=points)
                if self.section_detection_enabled:
                    section_counts = {}
                    for p in points:
                        sec = p.payload.get('section', 'unknown')
                        section_counts[sec] = section_counts.get(sec, 0) + 1
                    print(f"  Ingested {len(points)} chunks into '{collection_name}' | sections: {section_counts}")
                else:
                    print(f"  Ingested {len(points)} chunks into '{collection_name}'")
                return True
            print(f"  No valid chunks created for {file_path}")
            return False
        except Exception as e:
            print(f"Error ingesting PDF {file_path}: {e}")
            import traceback; traceback.print_exc()
            return False

    def ingest_md_file(self, file_path: str) -> bool:
        try:
            print(f"Ingesting MD: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
            if not text or len(text.strip()) < 10:
                print(f"  Warning: No content extracted from {file_path}")
                return False

            file_metadata = self.metadata_extractor.extract_metadata_from_path(file_path)
            collection_name = self._get_collection_for_doc_type(file_metadata['DocumentType'])

            doc_id = generate_doc_id(file_path)
            source_path = get_normalized_path(file_path)
            last_modified = datetime.fromtimestamp(os.stat(file_path).st_mtime).isoformat()
            title = Path(file_path).stem
            for line in text.split('\n')[:5]:
                if line.startswith('# '):
                    title = line[2:].strip()
                    break
            self.docstore.put(doc_id, text, {
                'source_path': source_path,
                'title': title,
                'collection_name': collection_name,
                'last_modified': last_modified,
                'content_type': 'markdown',
            })

            section_boundaries = []
            if self.section_detection_enabled:
                section_boundaries = self._find_section_boundaries(text)
                print(f"  Found {len(section_boundaries)} section boundaries")

            chunk_data = self.chunker.chunk_text(text, {**file_metadata, 'doc_id': doc_id, 'source_path': source_path})
            points = []
            last_position = 0

            for i, (chunk_text, chunk_metadata) in enumerate(chunk_data):
                embedding = self._get_embedding(chunk_text)
                if not embedding:
                    continue
                if self.section_detection_enabled and section_boundaries:
                    chunk_position = self._find_chunk_position(chunk_text, text, last_position)
                    chunk_metadata['section'] = self._get_section_for_position(chunk_position, section_boundaries)
                    last_position = chunk_position
                chunk_metadata['chunk_text'] = chunk_text
                chunk_metadata['chunk_index'] = i
                chunk_metadata['total_chunks'] = len(chunk_data)
                points.append(PointStruct(
                    id=self._generate_chunk_id(doc_id, i),
                    vector=embedding,
                    payload=chunk_metadata,
                ))

            if points:
                self.client.upsert(collection_name=collection_name, points=points)
                if self.section_detection_enabled:
                    section_counts = {}
                    for p in points:
                        sec = p.payload.get('section', 'unknown')
                        section_counts[sec] = section_counts.get(sec, 0) + 1
                    print(f"  Ingested {len(points)} chunks into '{collection_name}' | sections: {section_counts}")
                else:
                    print(f"  Ingested {len(points)} chunks into '{collection_name}'")
                return True
            print(f"  No valid chunks created for {file_path}")
            return False
        except Exception as e:
            print(f"Error ingesting MD {file_path}: {e}")
            import traceback; traceback.print_exc()
            return False

    def ingest_json_file(self, file_path: str) -> bool:
        try:
            import json
            print(f"Ingesting JSON: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                raw = f.read()
            json_data = json.loads(raw)

            file_metadata = self.metadata_extractor.extract_metadata_from_path(file_path)
            collection_name = self._get_collection_for_doc_type(file_metadata['DocumentType'])
            content_items = self.json_extractor.extract_content_for_embedding(json_data)
            if not content_items:
                print(f"  Warning: No content extracted from {file_path}")
                return False

            doc_id = generate_doc_id(file_path)
            source_path = get_normalized_path(file_path)
            last_modified = datetime.fromtimestamp(os.stat(file_path).st_mtime).isoformat()
            self.docstore.put(doc_id, raw, {
                'source_path': source_path,
                'title': file_metadata.get('title', Path(file_path).stem),
                'collection_name': collection_name,
                'last_modified': last_modified,
                'content_type': 'json',
            })

            total_chunks = len(content_items)
            points = []
            for i, item in enumerate(content_items):
                embedding = self._get_embedding(item['text'])
                if not embedding:
                    continue
                meta = {
                    **file_metadata,
                    'doc_id': doc_id,
                    'source_path': source_path,
                    'chunk_index': i,
                    'section_type': item.get('section_type', 'unknown'),
                    'section_name': item.get('section_name', 'Unknown Section'),
                    'section_classification': item.get('section_classification', 'Program Requirements'),
                    'content_type': 'structured_json',
                    'chunk_text': item['text'],
                    'total_chunks': total_chunks,
                }
                points.append(PointStruct(
                    id=self._generate_chunk_id(doc_id, i),
                    vector=embedding,
                    payload=meta,
                ))

            if points:
                self.client.upsert(collection_name=collection_name, points=points)
                print(f"  Ingested {len(points)} chunks into '{collection_name}'")
                return True
            print(f"  No valid chunks created for {file_path}")
            return False
        except Exception as e:
            print(f"Error ingesting JSON {file_path}: {e}")
            import traceback; traceback.print_exc()
            return False

    def ingest_file(self, file_path: str) -> bool:
        ext = Path(file_path).suffix.lower()
        if ext == '.md':
            return self.ingest_md_file(file_path)
        elif ext == '.pdf':
            return self.ingest_pdf_file(file_path)
        elif ext == '.json':
            return self.ingest_json_file(file_path)
        print(f"Unsupported file type: {ext}")
        return False

    def ingest_directory(self, directory: str, file_extensions: List[str] = None) -> Dict:
        if file_extensions is None:
            file_extensions = ['.pdf', '.json', '.md']
        stats = {'total_files': 0, 'success_files': 0, 'failed_files': 0, 'collections_used': set()}
        directory = Path(directory)
        if not directory.exists():
            print(f"Directory not found: {directory}")
            return stats
        for file_path in directory.rglob('*'):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in file_extensions:
                continue
            if 'readme' in file_path.name.lower() or file_path.name.startswith('._'):
                continue
            stats['total_files'] += 1
            if self.ingest_file(str(file_path)):
                stats['success_files'] += 1
                file_metadata = self.metadata_extractor.extract_metadata_from_path(str(file_path))
                stats['collections_used'].add(self._get_collection_for_doc_type(file_metadata['DocumentType']))
            else:
                stats['failed_files'] += 1
        return stats


UnifiedIngestion = FSEIngestion

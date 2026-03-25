import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fse_ingestion.fse_edit_metadata import FSEMetadataExtractor
from fse_utils.config_loader import load_config
from fse_utils.ollama_api import get_ollama_api
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
                    print(f"Collection '{collection_name}' wrong dimension ({existing_dim} vs {dimension}), recreating...")
                    self.client.delete_collection(collection_name)
                    needs_create = True
                else:
                    print(f"Collection '{collection_name}' exists (dim={existing_dim})")
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
                print(f"Created collection '{collection_name}' (dim={dimension})")

    # --- section detection ---

    def _load_section_patterns(self):
        section_config = self.config.get('ingestion', {}).get('section_detection', {})
        self.section_detection_enabled = section_config.get('enabled', True)
        self.default_section = section_config.get('default_section', 'general')
        patterns = section_config.get('patterns', [])
        self.section_patterns = (
            [(re.compile(p['pattern'], re.IGNORECASE), p['section']) for p in patterns]
            if patterns else self._get_default_section_patterns()
        )

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
        for length in (100, 50):
            pos = full_text.find(chunk_text[:length].strip(), start_from)
            if pos != -1:
                return pos
        return start_from

    # --- shared ingestion core ---

    def _put_docstore(self, file_path: str, text: str, file_metadata: dict,
                      collection_name: str, content_type: str) -> str:
        doc_id = generate_doc_id(file_path)
        source_path = get_normalized_path(file_path)
        last_modified = datetime.fromtimestamp(os.stat(file_path).st_mtime).isoformat()
        title = file_metadata.get('title', Path(file_path).stem)
        docstore_meta = {
            'source_path': source_path,
            'title': title,
            'collection_name': collection_name,
            'last_modified': last_modified,
            'content_type': content_type,
        }
        self.docstore.put(doc_id, text, docstore_meta)
        print(f"  [docstore] doc_id={doc_id} | collection={collection_name} | title={title!r} | type={content_type}")
        return doc_id

    def _upsert_chunks(self, chunk_data: List, full_text: str,
                       doc_id: str, collection_name: str,
                       section_boundaries: List) -> bool:
        points = []
        last_position = 0
        for i, (chunk_text, chunk_metadata) in enumerate(chunk_data):
            embedding = self._get_embedding(chunk_text)
            if not embedding:
                continue
            if section_boundaries:
                pos = self._find_chunk_position(chunk_text, full_text, last_position)
                chunk_metadata['section'] = self._get_section_for_position(pos, section_boundaries)
                last_position = pos
            chunk_metadata.update({
                'chunk_text': chunk_text,
                'chunk_index': i,
                'total_chunks': len(chunk_data),
            })
            points.append(PointStruct(
                id=self._generate_chunk_id(doc_id, i),
                vector=embedding,
                payload=chunk_metadata,
            ))

        if not points:
            return False

        self.client.upsert(collection_name=collection_name, points=points)

        # Log first chunk metadata as a sample for verification
        sample = points[0].payload
        key_meta = {k: sample[k] for k in (
            'DocumentType', 'SubjectCode', 'Year', 'section', 'chunk_index', 'total_chunks', 'source_path'
        ) if k in sample}
        section_counts = {}
        for p in points:
            sec = p.payload.get('section', 'none')
            section_counts[sec] = section_counts.get(sec, 0) + 1
        print(f"  [chunks] {len(points)} → '{collection_name}' | sample meta: {key_meta}")
        if section_counts:
            print(f"  [sections] {section_counts}")
        return True

    def _ingest_text(self, file_path: str, text: str,
                     file_metadata: dict, content_type: str) -> bool:
        collection_name = self._get_collection_for_doc_type(file_metadata['DocumentType'])
        doc_id = self._put_docstore(file_path, text, file_metadata, collection_name, content_type)
        source_path = get_normalized_path(file_path)

        section_boundaries = (
            self._find_section_boundaries(text) if self.section_detection_enabled else []
        )
        if self.section_detection_enabled:
            print(f"  Found {len(section_boundaries)} section boundaries")

        chunk_data = self.chunker.chunk_text(
            text, {**file_metadata, 'doc_id': doc_id, 'source_path': source_path}
        )
        return self._upsert_chunks(chunk_data, text, doc_id, collection_name, section_boundaries)

    # --- file-type ingestion ---

    def ingest_pdf_file(self, file_path: str) -> bool:
        try:
            print(f"Ingesting PDF: {file_path}")
            text, tika_metadata = extract_content(file_path)
            if not text or len(text.strip()) < 10:
                print(f"  Warning: No content extracted from {file_path}")
                return False
            file_metadata = self.metadata_extractor.extract_metadata_from_path(file_path)
            print(f"  [meta] type={file_metadata.get('DocumentType')} | subject={file_metadata.get('SubjectCode')} | year={file_metadata.get('Year')}")
            # Tika fills in extra fields (title, etc.) but must not overwrite our extracted metadata
            file_metadata = {**tika_metadata, **file_metadata}
            return self._ingest_text(file_path, text, file_metadata, 'pdf')
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
            print(f"  [meta] type={file_metadata.get('DocumentType')} | subject={file_metadata.get('SubjectCode')} | year={file_metadata.get('Year')}")
            # Use first H1 heading as title if present
            for line in text.split('\n')[:5]:
                if line.startswith('# '):
                    file_metadata['title'] = line[2:].strip()
                    break
            return self._ingest_text(file_path, text, file_metadata, 'markdown')
        except Exception as e:
            print(f"Error ingesting MD {file_path}: {e}")
            import traceback; traceback.print_exc()
            return False

    def ingest_json_file(self, file_path: str) -> bool:
        try:
            print(f"Ingesting JSON: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                raw = f.read()
            json_data = json.loads(raw)

            file_metadata = self.metadata_extractor.extract_metadata_from_path(file_path)
            print(f"  [meta] type={file_metadata.get('DocumentType')} | subject={file_metadata.get('SubjectCode')} | year={file_metadata.get('Year')}")
            collection_name = self._get_collection_for_doc_type(file_metadata['DocumentType'])
            content_items = self.json_extractor.extract_content_for_embedding(json_data)
            if not content_items:
                print(f"  Warning: No content extracted from {file_path}")
                return False

            doc_id = self._put_docstore(file_path, raw, file_metadata, collection_name, 'json')
            source_path = get_normalized_path(file_path)

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
                    'total_chunks': len(content_items),
                    'section_type': item.get('section_type', 'unknown'),
                    'section_name': item.get('section_name', 'Unknown Section'),
                    'section_classification': item.get('section_classification', 'Program Requirements'),
                    'content_type': 'structured_json',
                    'chunk_text': item['text'],
                }
                points.append(PointStruct(
                    id=self._generate_chunk_id(doc_id, i),
                    vector=embedding,
                    payload=meta,
                ))

            if not points:
                print(f"  No valid chunks created for {file_path}")
                return False

            self.client.upsert(collection_name=collection_name, points=points)
            sample = points[0].payload
            key_meta = {k: sample[k] for k in (
                'DocumentType', 'SubjectCode', 'Year', 'section_type', 'section_name', 'chunk_index', 'total_chunks'
            ) if k in sample}
            print(f"  [chunks] {len(points)} → '{collection_name}' | sample meta: {key_meta}")
            return True
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

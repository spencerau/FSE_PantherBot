import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
from textwrap import dedent

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from core_rag.ingestion.ingest import UnifiedIngestion
from core_rag.utils.doc_id import generate_doc_id, get_normalized_path
from core_rag.ingestion.chunking import AdvancedChunker
from core_rag.ingestion.embedding import EmbeddingGenerator
from core_rag.ingestion.file_ingest import FileIngestor
from core_rag.ingestion.json_extract import JSONContentExtractor
from core_rag.utils.docstore import get_docstore
from fse_ingestion.fse_edit_metadata import FSEMetadataExtractor
from fse_utils.config_loader import load_config

try:
    from core_rag.summary import SummaryIndexer, LLAMAINDEX_AVAILABLE
    from core_rag.utils.llm_api import get_ollama_api
    from core_rag.utils.docstore import get_docstore as _get_docstore_summary

    class FSESummaryIndexer(SummaryIndexer):
        def __init__(self, config, client):
            # Do NOT call super().__init__() — it calls core_rag's load_config()
            self.config = config
            self.client = client
            self.base_dir = None
            self.embedding_model = config['embedding']['model']
            self.ollama_api = get_ollama_api()
            self.docstore = _get_docstore_summary()
            summary_config = config.get('summary', {})
            self.summary_word_count = summary_config.get('word_count', 175)
            self.embed_summaries = summary_config.get('embed_summaries', True)
            self.llm_config = config.get('llm', {})
            self._int_llm_config = config.get('intermediate_llm', {})
            self._ensure_summary_collections()

        def generate_summary(self, text: str, title: str = None) -> str:
            model = self._int_llm_config.get('model', self.llm_config.get('primary_model', 'llama3.2'))
            prompt = dedent(f"""
                Summarize the following document in approximately {self.summary_word_count} words.
                Focus on the key topics, main points, and important details.

                {"Title: " + title if title else ""}

                Document:
                {text[:8000]}

                Summary:
            """).strip()
            try:
                messages = [{'role': 'user', 'content': prompt}]
                resp = self.ollama_api.chat(
                    model=model,
                    messages=messages,
                    stream=False,
                    think=False,
                    options={'num_predict': 512, 'temperature': 0.3}
                )
                return (resp or '').strip()
            except Exception as e:
                print(f"Error generating summary: {e}")
                return ""

        def index_document(self, file_path: str, collection_name: str) -> bool:
            try:
                if file_path.endswith('.pdf'):
                    reader = PdfReader(file_path)
                    text = '\n'.join(page.extract_text() or '' for page in reader.pages)
                else:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text = f.read()

                if not text or len(text.strip()) < 50:
                    return False

                doc_id = generate_doc_id(file_path, self.base_dir)
                source_path = get_normalized_path(file_path, self.base_dir)
                title = Path(file_path).stem

                if file_path.endswith('.md'):
                    for line in text.split('\n')[:5]:
                        if line.startswith('# '):
                            title = line[2:].strip()
                            break

                summary = self.generate_summary(text, title)
                if not summary:
                    return False

                file_stat = os.stat(file_path)
                last_modified = datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                summary_collection = self._get_summary_collection_name(collection_name)

                payload = {
                    'doc_id': doc_id, 'source_path': source_path, 'collection_name': collection_name,
                    'title': title, 'last_modified': last_modified, 'summary': summary
                }

                if self.embed_summaries:
                    embedding = self._get_embedding(summary)
                    if not embedding:
                        return False
                    summary_id = hashlib.sha256(f"{doc_id}:summary".encode()).hexdigest()[:32]
                    point = PointStruct(id=summary_id, vector=embedding, payload=payload)
                    self.client.upsert(collection_name=summary_collection, points=[point])
                    print(f"Ingested summary for '{title}' into '{summary_collection}'")
                return True
            except Exception as e:
                print(f"Error indexing document summary {file_path}: {e}")
                return False

except ImportError:
    SummaryIndexer = None
    FSESummaryIndexer = None
    LLAMAINDEX_AVAILABLE = False


class FSEIngestion(UnifiedIngestion):

    def __init__(self):
        # Do NOT call super().__init__() — core_rag's config loader would resolve
        # to the wrong configs directory. Build components manually instead.
        self.config = load_config()
        self.client = QdrantClient(
            host=self.config['qdrant']['host'],
            port=self.config['qdrant']['port'],
            timeout=self.config['qdrant']['timeout'],
        )
        self.base_dir = None
        self.collection_name = None

        self.embedding_gen = EmbeddingGenerator(self.config)
        chunker = AdvancedChunker(self.config.get('chunker', {}))
        json_extractor = JSONContentExtractor(self.config)
        docstore = get_docstore()
        metadata_extractor = FSEMetadataExtractor()

        coll_cfg = self.config.get('collection_config', {})
        self.enable_summaries = any(v.get('summary_enabled', False) for v in coll_cfg.values())
        if self.enable_summaries and LLAMAINDEX_AVAILABLE and FSESummaryIndexer:
            try:
                self.summary_indexer = FSESummaryIndexer(self.config, self.client)
                print("Summary indexer initialized")
            except Exception as e:
                print(f"Warning: Could not initialize summary indexer: {e}")
                self.summary_indexer = None
        else:
            self.summary_indexer = None

        self._ensure_collections_exist()

        self.file_ingestor = FileIngestor(
            client=self.client,
            config=self.config,
            embedding_gen=self.embedding_gen,
            chunker=chunker,
            json_extractor=json_extractor,
            docstore=docstore,
            metadata_extractor=metadata_extractor,
        )

    def ingest_file(self, file_path: str) -> bool:
        success = self.file_ingestor.ingest_file(file_path)

        if success and self.summary_indexer and file_path.endswith(('.md', '.txt', '.pdf')):
            collection_name = (
                self.collection_name
                or self.file_ingestor.get_last_used_collection()
                or list(self.config['qdrant']['collections'].values())[0]
            )
            name_to_key = {v: k for k, v in self.config['qdrant']['collections'].items()}
            collection_key = name_to_key.get(collection_name, collection_name)
            coll_cfg = self.config.get('collection_config', {})
            per_cfg = coll_cfg.get(collection_key, {})
            if per_cfg.get('summary_enabled', not coll_cfg):
                try:
                    self.summary_indexer.index_document(file_path, collection_name)
                except Exception as e:
                    print(f"Warning: Could not generate summary for {file_path}: {e}")

        return success


UnifiedIngestion = FSEIngestion
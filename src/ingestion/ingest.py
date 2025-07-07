import os
import re
from pathlib import Path
from typing import Dict, List
import sys
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from datetime import datetime
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.config_loader import load_config
from utils.ollama_api import get_ollama_api
from ingestion.content_extract import extract_content


class UnifiedIngestion:
    def __init__(self):
        self.config = load_config()
        self.client = QdrantClient(
            host=self.config['qdrant']['host'],
            port=self.config['qdrant']['port'],
            timeout=self.config['qdrant']['timeout']
        )
        self.embedding_model = self.config['embedding']['model']
        self.chunk_size = self.config['embedding']['chunk_size']
        self.chunk_overlap = self.config['embedding']['chunk_overlap']
        self.ollama_api = get_ollama_api()
        
        self._ensure_collections_exist()
    
    def _ensure_collections_exist(self):
        collections = self.config['qdrant']['collections']
        
        for collection_name in collections.values():
            try:
                self.client.get_collection(collection_name)
                print(f"Collection '{collection_name}' already exists")
            except Exception:
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=768,
                        distance=Distance.COSINE
                    )
                )
                print(f"Created collection '{collection_name}'")
    
    def _get_embedding(self, text: str) -> List[float]:
        try:
            embedding = self.ollama_api.get_embeddings(
                model=self.embedding_model,
                prompt=text
            )
            return embedding
        except Exception as e:
            print(f"Error getting embedding: {e}")
            return None
    
    def _chunk_text(self, text: str) -> List[str]:
        words = text.split()
        chunks = []
        current_chunk = []
        current_size = 0
        
        for word in words:
            if current_size + len(word) + 1 > self.chunk_size:
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                    overlap_words = int(self.chunk_overlap / 10)
                    current_chunk = current_chunk[-overlap_words:] if overlap_words > 0 else []
                    current_size = sum(len(w) + 1 for w in current_chunk)
            
            current_chunk.append(word)
            current_size += len(word) + 1
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _extract_metadata_from_path(self, file_path: str) -> Dict:
        path = Path(file_path)
        metadata = {
            'file_name': path.name,
            'file_path': str(path),
            'file_extension': path.suffix,
            'ingested_at': datetime.now().isoformat()
        }
        
        match = re.search(r'(\d{4})_(.+)\.pdf', path.name)
        if match:
            metadata['year'] = match.group(1)
            subject_part = match.group(2)
            metadata['subject'] = subject_part.replace('_', ' ')
            
            program_mappings = {
                'Computer Science': 'cs',
                'Computer Engineering': 'ce',
                'Software Engineering': 'se',
                'Electrical Engineering': 'ee',
                'Data Science': 'ds'
            }
            
            for full_name, code in program_mappings.items():
                if full_name in metadata['subject']:
                    metadata['program'] = code
                    metadata['program_full'] = full_name
                    break
        
        if 'major_catalogs' in str(path).lower():
            metadata['collection_type'] = 'major_catalogs'
            metadata['document_type'] = 'major'
        elif 'minor_catalogs' in str(path).lower():
            metadata['collection_type'] = 'minor_catalogs'
            metadata['document_type'] = 'minor'
        elif 'course_catalogs' in str(path) or 'course_listings' in str(path):
            metadata['collection_type'] = 'course_listings'
            metadata['document_type'] = 'course'
        elif 'general_knowledge' in str(path).lower():
            metadata['collection_type'] = 'general_knowledge'
            metadata['document_type'] = 'general'
        else:
            metadata['collection_type'] = 'general_knowledge'
            metadata['document_type'] = 'general'
        
        return metadata
    
    def ingest_file(self, file_path: str) -> bool:
        try:
            print(f"Ingesting: {file_path}")
            
            text, tika_metadata = extract_content(file_path)
            if not text or len(text.strip()) < 10:
                print(f"  Warning: No content extracted from {file_path}")
                return False
            
            file_metadata = self._extract_metadata_from_path(file_path)
            combined_metadata = {**tika_metadata, **file_metadata}
            
            collection_name = self.config['qdrant']['collections'][combined_metadata['collection_type']]
            
            chunks = self._chunk_text(text)
            
            points = []
            for i, chunk in enumerate(chunks):
                embedding = self._get_embedding(chunk)
                if embedding is None:
                    continue
                
                chunk_metadata = combined_metadata.copy()
                chunk_metadata['chunk_id'] = i
                chunk_metadata['chunk_text'] = chunk
                chunk_metadata['total_chunks'] = len(chunks)
                
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload=chunk_metadata
                )
                points.append(point)
            
            if points:
                self.client.upsert(
                    collection_name=collection_name,
                    points=points
                )
                print(f"  ✓ Ingested {len(points)} chunks into collection '{collection_name}'")
                return True
            else:
                print(f"  ✗ No valid chunks created for {file_path}")
                return False
                
        except Exception as e:
            print(f"  ✗ Error ingesting {file_path}: {e}")
            return False
    
    def ingest_directory(self, directory: str, file_extensions: List[str] = None) -> Dict:
        if file_extensions is None:
            file_extensions = ['.pdf']
        
        stats = {
            'total_files': 0,
            'success_files': 0,
            'failed_files': 0,
            'collections_used': set()
        }
        
        directory = Path(directory)
        if not directory.exists():
            print(f"Directory not found: {directory}")
            return stats
        
        for file_path in directory.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in file_extensions:
                if 'readme' in file_path.name.lower():
                    continue
                    
                stats['total_files'] += 1
                
                if self.ingest_file(str(file_path)):
                    stats['success_files'] += 1
                else:
                    stats['failed_files'] += 1
        
        return stats
    
    def bulk_ingest(self, data_directories: List[str]) -> Dict:
        total_stats = {
            'total_files': 0,
            'success_files': 0,
            'failed_files': 0,
            'collections_used': set()
        }
        
        for directory in data_directories:
            print(f"\n=== Ingesting from {directory} ===")
            stats = self.ingest_directory(directory)
            
            total_stats['total_files'] += stats['total_files']
            total_stats['success_files'] += stats['success_files']
            total_stats['failed_files'] += stats['failed_files']
            total_stats['collections_used'].update(stats['collections_used'])
            
            print(f"Directory stats: {stats['success_files']}/{stats['total_files']} files successful")
        
        return total_stats
    
    def print_collection_summary(self):
        print("\n=== Collection Summary ===")
        collections = self.config['qdrant']['collections']
        
        for collection_name in collections.values():
            try:
                info = self.client.get_collection(collection_name)
                print(f"{collection_name}: {info.points_count} documents")
            except Exception as e:
                print(f"{collection_name}: Error - {e}")
    
    def clear_collections(self):
        collections = self.config['qdrant']['collections']
        
        for collection_name in collections.values():
            try:
                self.client.delete_collection(collection_name)
                print(f"Deleted collection '{collection_name}'")
            except Exception as e:
                print(f"Error deleting collection '{collection_name}': {e}")
        
        self._ensure_collections_exist()


def main():
    print("Starting unified RAG ingestion...")
    
    ingestion = UnifiedIngestion()
    
    config = load_config()
    data_dirs = [
        config['data']['major_catalogs_path'],
        config['data']['minor_catalogs_path'],
        config['data']['course_catalogs_path']
    ]
    
    if os.path.exists(config['data']['general_knowledge_path']):
        data_dirs.append(config['data']['general_knowledge_path'])
    
    stats = ingestion.bulk_ingest(data_dirs)
    
    print(f"\n=== Final Results ===")
    print(f"Total files processed: {stats['total_files']}")
    print(f"Successfully ingested: {stats['success_files']}")
    print(f"Failed: {stats['failed_files']}")
    
    ingestion.print_collection_summary()


if __name__ == "__main__":
    main()

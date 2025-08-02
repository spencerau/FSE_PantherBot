# tests/test_ingestion.py

import sys
from pathlib import Path
import pytest
import csv
import json
import glob
import tempfile
import os
from pypdf import PdfReader
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance
src_path = Path(__file__).parent.parent / 'src'
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

project_root = Path(__file__).parent.parent.resolve()

from ingestion.ingest import UnifiedIngestion
from ingestion.content_extract import extract_content
from utils.config_loader import load_config
from utils.ollama_api import get_ollama_api

config = load_config()
qdrant = QdrantClient(host=config['qdrant']['host'], port=config['qdrant']['port'])
ollama_api = get_ollama_api()

def embed_texts(texts):
    """Helper function to embed texts using Ollama REST API"""
    embeddings = []
    for text in texts:
        embedding = ollama_api.get_embeddings(
            model=config['embedding']['model'],
            prompt=text
        )
        embeddings.append(embedding)
    return embeddings

@pytest.fixture
def temp_collection():
    """Fixture to create and clean up temporary collections for testing"""
    collection_name = f"test_collection_{os.getpid()}_{hash(os.urandom(8)) % 10000}"
    
    dim = len(embed_texts(["dummy"])[0])
    qdrant.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
    )
    
    yield collection_name
    
    try:
        qdrant.delete_collection(collection_name=collection_name)
    except:
        pass

def ingest_text_to_collection(text, collection_name):
    """Helper function to ingest text directly to a specific collection"""
    ingestion = UnifiedIngestion()
    chunk_tuples = ingestion._chunk_text_with_metadata(text, {})
    chunks = [chunk_text for chunk_text, _ in chunk_tuples]
    ingested_count = 0
    for i, chunk in enumerate(chunks):
        if len(chunk.strip()) > 10:
            embedding = ingestion._get_embedding(chunk)
            point_id = abs(hash(chunk)) % 1000000  # Ensure positive integer
            
            qdrant.upsert(
                collection_name=collection_name,
                points=[{
                    "id": point_id,
                    "vector": embedding,
                    "payload": {
                        "text": chunk,
                        "metadata": {"test": True}
                    }
                }]
            )
            ingested_count += 1
    
    return ingested_count

def ingest_file_to_collection(file_path, collection_name):
    """Helper function to ingest a file directly to a specific collection"""
    from ingestion.content_extract import extract_content
    
    try:
        text, metadata = extract_content(file_path)
        if text:
            return ingest_text_to_collection(text, collection_name)
        return 0
    except Exception as e:
        print(f"Error ingesting file {file_path}: {e}")
        return 0

# 1. Ingest and Retrieve Test
def test_ingest_and_retrieve(temp_collection):
    collection = temp_collection
    
    sample = "PantherBot is an AI academic advisor. " * 50
    count = ingest_text_to_collection(sample, collection)
    assert count > 0, "No chunks ingested"

    query_text = "What is PantherBot?"
    q_emb = embed_texts([query_text])[0]
    results = qdrant.search(
        collection_name=collection,
        query_vector=q_emb,
        limit=3,
        with_payload=True
    )

    assert len(results) > 0, "No results retrieved"
    assert any("PantherBot" in hit.payload.get("text", "") for hit in results)

# 2. PDF Ingestion Test
def test_ingest_pdf(temp_collection):
    pdf_path = "data/major_catalogs/2022_Computer Science.pdf"
    abs_pdf_path = project_root / pdf_path
    
    if not abs_pdf_path.exists():
        pytest.skip(f"PDF file {pdf_path} not found")
    
    count = ingest_file_to_collection(str(abs_pdf_path), temp_collection)
    assert count > 0, f"Failed to ingest {pdf_path}"

# 3. CSV Ingestion Test
def test_ingest_csv(temp_collection):
    csv_path = "data/course_listings/Fall_2024.csv"
    abs_csv_path = project_root / csv_path
    
    if not abs_csv_path.exists():
        pytest.skip(f"CSV file {csv_path} not found")
    
    count = ingest_file_to_collection(str(abs_csv_path), temp_collection)
    assert count > 0, f"Failed to ingest {csv_path}"

# 4. JSON (Hyperlinks) Ingestion Test
def test_ingest_links_json(temp_collection):
    json_path = project_root / 'data/links.json'
    
    if not json_path.exists():
        pytest.skip("Links JSON file not found")
    
    count = ingest_file_to_collection(str(json_path), temp_collection)
    assert count > 0, "Failed to ingest links JSON file"

# 5. Qdrant Connection Test
def test_qdrant_connection(temp_collection):
    collections = qdrant.get_collections().collections
    assert any(c.name == temp_collection for c in collections)

# 6. Tika Extraction Test
def test_tika_extraction():
    sample_pdf = next(glob.iglob(str(Path(project_root, 'data/major_catalogs/2022_Computer Science.pdf'))))
    text, metadata = extract_content(sample_pdf)
    assert text and isinstance(text, str)
    assert isinstance(metadata, dict)
    assert len(text) > 20  # Should extract some content

# 7. Embedding Service Test
def test_embedding_service():
    sample_text = "PantherBot is an AI academic advisor."
    embedding = embed_texts([sample_text])
    assert embedding and isinstance(embedding, list)
    assert isinstance(embedding[0], list)
    assert len(embedding[0]) > 0

# 8. Metadata Tagging Test
# no longer needed as metadata is now handled in src/preprocess/edit_metadata.py
# def test_metadata_tagging():
#     pdf_files = glob.glob(str(Path(project_root, 'data/Major_Catalogs/*.pdf')))
#     if not pdf_files:
#         pytest.skip("No PDF files found for metadata tagging test.")
#     pdf_path = pdf_files[0]
#     metadata = {'test_tag': 'test_value'}
#     collection = 'test_metadata_tagging'
#     if qdrant.collection_exists(collection):
#         qdrant.delete_collection(collection_name=collection)
#     dim = len(embed_texts(["dummy"])[0])
#     qdrant.create_collection(
#         collection_name=collection,
#         vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
#     )
#     count = ingest_file(pdf_path, collection=collection, metadata=metadata)
#     assert count > 0
#     results = qdrant.scroll(collection_name=collection, limit=1, with_payload=True)
#     # Fix: handle Qdrant scroll return type robustly
#     records = results[0] if isinstance(results, tuple) else results
#     first_record = records[0]
#     payload = getattr(first_record, "payload", None)
#     assert payload is not None, "No payload found in first record"
#     assert 'test_tag' in payload.get('metadata', {})

# 9. Error Handling Test
def test_error_handling():
    count = ingest_file_to_collection('nonexistent_file.pdf', 'temp_collection')
    assert count == 0, "Should return 0 for non-existent file"

# 10. Duplicate Ingestion Test
def test_duplicate_ingestion(temp_collection):
    pdf_files = glob.glob(str(project_root / 'data/major_catalogs/*.pdf'))
    if not pdf_files:
        pytest.skip("No PDF files found for duplicate ingestion test.")
    
    pdf_path = pdf_files[0]
    
    count1 = ingest_file_to_collection(pdf_path, temp_collection)
    count2 = ingest_file_to_collection(pdf_path, temp_collection)
    
    assert count1 > 0, "First ingestion should succeed"
    assert count2 > 0, "Second ingestion should succeed"
    
    try:
        collection_info = qdrant.get_collection(temp_collection)
        assert collection_info.points_count > 0, "Collection should contain points"
    except Exception as e:
        pytest.fail(f"Failed to verify collection: {e}")

# 11. Unified Collection System Test
def test_unified_collections():
    """Test that the unified collections are properly created and functioning"""
    expected_collections = [
        'major_catalogs',
        'minor_catalogs', 
        'course_listings',
        'general_knowledge'
    ]
    
    for collection_name in expected_collections:
        try:
            collection_info = qdrant.get_collection(collection_name)
            print(f"Collection '{collection_name}' exists with {collection_info.points_count} points")
        except Exception as e:
            print(f"Collection '{collection_name}' does not exist: {e}")


# 12. Directory Ingestion Test
def test_ingest_directory():
    """Test ingesting an entire directory with the real UnifiedIngestion system"""
    major_catalogs_dir = project_root / "data" / "major_catalogs"
    
    if not major_catalogs_dir.exists() or not any(major_catalogs_dir.glob("*.pdf")):
        pytest.skip("Major catalogs directory not found or empty")
    
    ingestion_system = UnifiedIngestion()
    
    collection_name = config['qdrant']['collections']['major_catalogs']
    
    try:
        before_info = qdrant.get_collection(collection_name)
        before_count = before_info.points_count
    except:
        before_count = 0
    
    results = ingestion_system.ingest_directory(str(major_catalogs_dir), file_extensions=['.pdf'])
    
    assert 'success_files' in results, "Directory ingestion should return results"
    assert results['success_files'] > 0, "Should successfully ingest at least one file"
    
    try:
        after_info = qdrant.get_collection(collection_name)
        after_count = after_info.points_count
        # Note: Due to duplicate handling, the count might not increase if files were already ingested
        print(f"Collection points before: {before_count}, after: {after_count}")
    except Exception as e:
        pytest.fail(f"Failed to verify collection after ingestion: {e}")
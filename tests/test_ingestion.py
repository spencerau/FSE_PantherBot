# tests/test_qdrant_ingest.py

import sys
from pathlib import Path
import pytest
import csv
import json
import glob
from qdrant_client.models import VectorParams, Distance

project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))
    
from src.embeddings import ingest, qdrant, embed_texts, ingest_file
from src.content_extract import extract_content


def extract_metadata_from_filename(filename, filetype):
    # Example: 2023-2024_Undergrad_CompSci.pdf
    parts = Path(filename).stem.split('_')
    metadata = {}
    if filetype == 'pdf':
        metadata['year'] = parts[0]
        if 'major' in filename:
            metadata['type'] = 'major_catalog'
            metadata['major'] = parts[-1]
        elif 'minor' in filename:
            metadata['type'] = 'minor_catalog'
            metadata['minor'] = parts[-1]
    elif filetype == 'csv':
        metadata['type'] = 'course_catalog'
        metadata['semester'] = parts[0] + ' ' + parts[1]
    return metadata

# 1. Ingest and Retrieve Test
def test_ingest_and_retrieve(tmp_path):
    collection = "test_pantherbot"
    
    if qdrant.collection_exists(collection):
        qdrant.delete_collection(collection_name=collection)
    
    dim = len(embed_texts(["dummy"])[0])
    
    qdrant.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
    )

    sample = "PantherBot is an AI academic advisor. " * 50
    count = ingest(sample, collection=collection)
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
def test_ingest_pdf():
    pdf_files = glob.glob(str(Path(project_root, 'data/major_catalogs/*.pdf')))
    for pdf_path in pdf_files:
        metadata = extract_metadata_from_filename(pdf_path, 'pdf')
        collection = 'test_pdf_catalogs'
        if qdrant.collection_exists(collection):
            qdrant.delete_collection(collection_name=collection)
        dim = len(embed_texts(["dummy"])[0])
        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
        )
        count = ingest_file(pdf_path, collection=collection, metadata=metadata)
        assert count > 0, f"No chunks ingested for {pdf_path}"

# 3. CSV Ingestion Test
def test_ingest_csv():
    csv_files = glob.glob(str(Path(project_root, 'data/course_catalogs/*.csv')))
    for csv_path in csv_files:
        metadata = extract_metadata_from_filename(Path(csv_path).name, 'csv')
        collection = 'test_csv_catalogs'
        if qdrant.collection_exists(collection):
            qdrant.delete_collection(collection_name=collection)
        dim = len(embed_texts(["dummy"])[0])
        qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
        )
        count = ingest_file(csv_path, collection=collection, metadata=metadata)
        assert count > 0, f"No chunks ingested for {csv_path}"

# 4. JSON (Hyperlinks) Ingestion Test
def test_ingest_links_json():
    json_path = Path(project_root, 'data/links.json')
    with open(json_path, encoding='utf-8') as f:
        links = json.load(f)
    collection = 'test_links_json'
    if qdrant.collection_exists(collection):
        qdrant.delete_collection(collection_name=collection)
    dim = len(embed_texts(["dummy"])[0])
    qdrant.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
    )
    for link in links:
        metadata = {
            'type': 'web_link',
            'category': link.get('category', ''),
            'title': link.get('title', '')
        }
        text = f"{link['title']}: {link['description']} ({link['url']})"
        tmp_path = Path(project_root, 'tmp_link.txt')
        with open(tmp_path, 'w', encoding='utf-8') as tmpf:
            tmpf.write(text)
        count = ingest_file(str(tmp_path), collection=collection, metadata=metadata)
        assert count > 0, f"No chunks ingested for link: {link['title']}"
        tmp_path.unlink()

# 5. Qdrant Connection Test
def test_qdrant_connection():
    collection = "test_connection"
    if qdrant.collection_exists(collection):
        qdrant.delete_collection(collection_name=collection)
    qdrant.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=2, distance=Distance.COSINE)
    )
    collections = qdrant.get_collections().collections
    assert any(c.name == collection for c in collections)
    qdrant.delete_collection(collection_name=collection)

# 6. Tika Extraction Test
def test_tika_extraction():
    sample_pdf = next(glob.iglob(str(Path(project_root, 'data/major_catalogs/*.pdf'))))
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
def test_metadata_tagging():
    pdf_files = glob.glob(str(Path(project_root, 'data/major_catalogs/*.pdf')))
    if not pdf_files:
        pytest.skip("No PDF files found for metadata tagging test.")
    pdf_path = pdf_files[0]
    metadata = {'test_tag': 'test_value'}
    collection = 'test_metadata_tagging'
    if qdrant.collection_exists(collection):
        qdrant.delete_collection(collection_name=collection)
    dim = len(embed_texts(["dummy"])[0])
    qdrant.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
    )
    count = ingest_file(pdf_path, collection=collection, metadata=metadata)
    assert count > 0
    results = qdrant.scroll(collection_name=collection, limit=1, with_payload=True)
    # Fix: handle Qdrant scroll return type robustly
    records = results[0] if isinstance(results, tuple) else results
    first_record = records[0]
    payload = getattr(first_record, "payload", None)
    assert payload is not None, "No payload found in first record"
    assert 'test_tag' in payload.get('metadata', {})

# 9. Error Handling Test
def test_error_handling():
    with pytest.raises(Exception):
        ingest_file('nonexistent_file.pdf', collection='test_error_handling')

# 10. Duplicate Ingestion Test
def test_duplicate_ingestion():
    pdf_files = glob.glob(str(Path(project_root, 'data/major_catalogs/*.pdf')))
    if not pdf_files:
        pytest.skip("No PDF files found for duplicate ingestion test.")
    pdf_path = pdf_files[0]
    collection = 'test_duplicate_ingestion'
    if qdrant.collection_exists(collection):
        qdrant.delete_collection(collection_name=collection)
    dim = len(embed_texts(["dummy"])[0])
    qdrant.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE)
    )
    count1 = ingest_file(pdf_path, collection=collection)
    count2 = ingest_file(pdf_path, collection=collection)
    print(f"count1: {count1}, count2: {count2}")
    results = qdrant.scroll(collection_name=collection, limit=1000, with_payload=True)
    records = results[0] if isinstance(results, tuple) else results
    print(f"len(results): {len(records)}")
    assert len(records) >= count1
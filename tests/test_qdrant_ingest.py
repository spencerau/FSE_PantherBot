# tests/test_qdrant_ingest.py

import sys
from pathlib import Path
import pytest

project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.embeddings import ingest, qdrant, chunk_text, embed_texts


def test_ingest_and_retrieve(tmp_path):
    collection = "test_pantherbot"
    
    if qdrant.collection_exists(collection):
        qdrant.delete_collection(collection_name=collection)
    
    from qdrant_client.models import VectorParams, Distance
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
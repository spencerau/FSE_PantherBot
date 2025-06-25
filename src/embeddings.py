# src/embeddings.py
import os
import yaml
import requests
import tiktoken
import sys
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

current_file_path = Path(__file__).resolve()
src_dir = current_file_path.parent
if str(src_dir) not in sys.path:
    sys.path.append(str(src_dir))

from src.utils.config_loader import load_config


cfg = load_config()
embed_cfg = cfg.get("embedding", {})
EMBEDDING_MODEL = cfg.get("nomic-embed-text", {})
CHUNK_SIZE = embed_cfg.get("chunk_size", 400)
CHUNK_OVERLAP = embed_cfg.get("chunk_overlap", 80)

# Use environment variables with fallbacks for service hostnames
# In Docker: use service names, In local dev: use localhost
QDRANT_HOST = os.environ.get("QDRANT_HOST", "qdrant" if os.environ.get("DOCKER_ENV") else "localhost")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "ollama" if os.environ.get("DOCKER_ENV") else "localhost")

QDRANT_URL = cfg.get("qdrant", {}).get("url", f"http://{QDRANT_HOST}:6333")
COLLECTION = cfg.get("qdrant", {}).get("collection", "pantherbot")

ENC = tiktoken.get_encoding("cl100k_base")
qdrant = QdrantClient(url=QDRANT_URL)


def create_collection_if_not_exists(collection=None):
    collection_name = collection or COLLECTION
    size = encode_dummy_size()
    if not qdrant.collection_exists(collection_name):
        qdrant.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=size, distance=Distance.COSINE)
        )

def encode_dummy_size():
    dummy = embed_texts(["test"])[0]
    return len(dummy)

def chunk_text(text: str):
    tokens = ENC.encode(text)
    stride = CHUNK_SIZE - CHUNK_OVERLAP
    return [
        ENC.decode(tokens[i : i + CHUNK_SIZE])
        for i in range(0, len(tokens), stride)
        if tokens[i : i + CHUNK_SIZE]
    ]

def embed_texts(texts: list[str]):
    payload = {"model": embed_cfg["embed_model"], "texts": texts}
    resp = requests.post(f"http://{OLLAMA_HOST}:11434/api/embeddings", json=payload)
    resp.raise_for_status()
    return resp.json().get("embeddings", [])

def ingest(text: str, collection=None):
    collection_name = collection or COLLECTION
    create_collection_if_not_exists(collection_name)
    chunks = chunk_text(text)
    embs = embed_texts(chunks)
    points = [
        PointStruct(id=i, vector=embs[i], payload={"text": chunks[i]})
        for i in range(len(chunks))
    ]
    qdrant.upsert(collection_name=collection_name, points=points)
    return len(chunks)

if __name__ == "__main__":
    print("Ingested chunks:", ingest("This is a test document. " * 200))
# src/embeddings.py
import os
import yaml
import requests
import tiktoken
import sys
import uuid
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

current_file_path = Path(__file__).resolve()
src_dir = current_file_path.parent
if str(src_dir) not in sys.path:
    sys.path.append(str(src_dir))

from src.utils.config_loader import load_config
from src.content_extract import extract_chunks_and_metadata


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
    # changed to use proper API endpoint (embed and not embeddings)
    url = f"http://{OLLAMA_HOST}:11434/api/embed"
    payload = {"model": embed_cfg["embed_model"], "input": texts if len(texts) > 1 else texts[0]}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    data = resp.json()
    if "embeddings" in data:
        return data["embeddings"]
    elif "embedding" in data:
        return [data["embedding"]]
    else:
        return []

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

# changed to use Apache Tika for content extraction
def ingest_file(file_path: str, collection=None, metadata=None):
    collection_name = collection or COLLECTION
    create_collection_if_not_exists(collection_name)
    chunked = extract_chunks_and_metadata(
        file_path,
        user_metadata=metadata,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP
    )
    chunks = [c for c, m in chunked]
    metadatas = [m for c, m in chunked]
    embs = embed_texts(chunks)
    points = [
        PointStruct(id=str(uuid.uuid4()), vector=embs[i], payload={"text": chunks[i], "metadata": metadatas[i]})
        for i in range(len(chunks))
    ]
    qdrant.upsert(collection_name=collection_name, points=points)
    return len(chunks)

if __name__ == "__main__":
    print("Ingested chunks:", ingest("This is a test document. " * 200))
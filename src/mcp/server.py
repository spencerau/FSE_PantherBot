
import os
import sys
import yaml
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from fastmcp import FastMCP
from src.pipeline import (
    ingest_documents,
    reindex_collection,
    embed_query,
    retrieve_dense,
    retrieve_bm25,
    fuse_rrf,
    rerank_bge_m3,
    assemble_context,
    answer_with_context,
    list_collection_documents,
    read_document_resource,
)

def load_config():
    config_path = os.environ.get("MCP_CONFIG", "configs/config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config.get("mcp", {})

mcp = FastMCP("PantherBot MCP Server")

@mcp.tool
def health_check() -> dict:
    return {"ok": True}

@mcp.tool
def ingest_documents_tool(paths: list, collection: str) -> dict:
    count = ingest_documents(paths, collection)
    return {"count": count}

@mcp.tool
def reindex_collection_tool(collection: str) -> dict:
    reindex_collection(collection)
    return {"ok": True}

@mcp.tool
def embed_query_tool(query: str) -> dict:
    vector = embed_query(query)
    return {"vector": vector}

@mcp.tool
def retrieve_dense_tool(query: str, collection: str, k: int) -> dict:
    results = retrieve_dense(query, collection, k)
    return {"results": results}

@mcp.tool
def retrieve_bm25_tool(query: str, collection: str, k: int) -> dict:
    results = retrieve_bm25(query, collection, k)
    return {"results": results}

@mcp.tool
def fuse_rrf_tool(dense: list, sparse: list, rrf_k: int, weights: dict) -> dict:
    fused = fuse_rrf(dense, sparse, rrf_k, weights)
    return {"fused": fused}

@mcp.tool
def rerank_bge_m3_tool(query: str, candidates: list, top_k: int, batch_size: int) -> dict:
    results = rerank_bge_m3(query, candidates, top_k, batch_size)
    return {"results": results}

@mcp.tool
def assemble_context_tool(ids: list, max_tokens: int) -> dict:
    context, citations = assemble_context(ids, max_tokens)
    return {"context": context, "citations": citations}

@mcp.tool
def answer_with_context_tool(query: str, collection: str, k_dense: int, k_sparse: int, rrf_k: int, top_k_rerank: int) -> dict:
    answer, citations, debug = answer_with_context(query, collection, k_dense, k_sparse, rrf_k, top_k_rerank)
    return {"answer": answer, "citations": citations, "debug": debug}

@mcp.resource("resource://collections/<name>/documents")
def collection_documents_resource(uri: str, op: str):
    if op == "list":
        return list_collection_documents(uri)
    if op == "read":
        return read_document_resource(uri)
    return None

if __name__ == "__main__":
    mcp.run()

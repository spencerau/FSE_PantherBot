
from src.retrieval.reranker import BGEReranker

def ingest_documents(paths, collection):
    return 0

def reindex_collection(collection):
    pass

def embed_query(query):
    return []

def retrieve_dense(query, collection, k):
    return []

def retrieve_bm25(query, collection, k):
    return []

def fuse_rrf(dense, sparse, rrf_k, weights):
    return []

def rerank_bge_m3(query, candidates, top_k, batch_size):
    reranker = BGEReranker()
    docs = [{"id": c["id"], "text": c["text"]} for c in candidates]
    reranked = reranker.rerank(query, docs, top_k)
    return [{"id": d["id"], "score": d["rerank_score"]} for d in reranked]

def assemble_context(ids, max_tokens):
    return "", []

def answer_with_context(query, collection, k_dense, k_sparse, rrf_k, top_k_rerank):
    return "", [], {"dense": [], "sparse": [], "fused": [], "rerank": []}

def list_collection_documents(uri):
    return []

def read_document_resource(uri):
    return {"text": "", "metadata": {"source_id": "", "page": 0, "section_title": ""}}

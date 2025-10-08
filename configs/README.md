# Configuration Guide for FSE_PantherBot

This document explains each parameter in the `config.yaml` file used for configuring the FSE_PantherBot RAG system.

## System Configuration

```yaml
system:
  name: "Fowler School of Engineering Academic Advisor"
  version: "1.0.0"
  description: "Unified collection-based RAG system for academic advising"
```

Basic system metadata for identification and versioning.

## Qdrant Vector Database

```yaml
qdrant:
  host: "localhost"
  port: 6333
  timeout: 150
  collections:
    major_catalogs: "major_catalogs"
    minor_catalogs: "minor_catalogs"
    general_knowledge: "general_knowledge"
    4_year_plans: "4_year_plans"
```

- `host/port`: Qdrant database connection settings
- `timeout`: Connection timeout in seconds
- `collections`: Named collections for different document types

## Data Paths

```yaml
data:
  major_catalog_json_path: "data/major_catalog_json"
  general_knowledge_path: "data/general_knowledge"
  4_year_plans: "data/4_year_plans"
```

Directory paths for source documents to be ingested.

## Embedding Model

```yaml
embedding:
  model: "bge-m3:567m"  # Cluster model
  # model: "nomic-embed-text"  # Local fallback
  batch_size: 32
  ollama_host: "localhost"
  ollama_port: 11434
  add_prefixes: true
  lowercase: false
  normalize_unicode: true
  collapse_whitespace: true
  dehyphenate: true
```

- `model`: BGE-M3 for semantic embeddings (cluster) or Nomic-Embed (local)
- `batch_size`: Number of documents processed simultaneously
- `ollama_host/port`: Ollama service connection
- Text preprocessing flags for improved embedding quality

## Text Chunking

```yaml
chunker:
  strategy: "recursive"
  target_tokens: 1000
  min_tokens: 500
  overlap_ratio: 0.1
  respect_headings: true
```

- `strategy`: Chunking algorithm (recursive character splitting)
- `target_tokens`: Ideal chunk size
- `min_tokens`: Minimum acceptable chunk size
- `overlap_ratio`: Percentage overlap between chunks
- `respect_headings`: Preserve document structure

## LLM Configuration

```yaml
llm:
  model: "gpt-oss:120b"  # Current cluster model
  # model: "deepseek-r1:70b"  # Alternative
  # model: "gemma3:4b"  # Local fallback
  temperature: 0.2
  top_p: 0.7
  max_tokens: 6000
  context_length: 128000
  timeout: 600
  ollama_options:
    keep_alive: "30m"
    num_ctx: 128000
```

- `model`: GPT-OSS 120B for response generation
- `temperature`: Response randomness (0.2 = focused, deterministic)
- `top_p`: Nucleus sampling for token selection
- `max_tokens`: Maximum response length
- `context_length`: Maximum input context size
- `timeout`: Request timeout in seconds
- `ollama_options`: Ollama-specific settings

## Retrieval System

```yaml
retrieval:
  initial_top_k: 20
  final_top_k: 15
  enable_reranking: true
  
  # Collection weighting for dynamic allocation
  collection_weights:
    major_catalogs: 0.4
    minor_catalogs: 0.1
    4_year_plans: 0.35
    general_knowledge: 0.15
  
  # Per-collection limits
  min_chunks_per_collection: 5
  max_chunks_per_collection: 20
  total_retrieval_budget: 40
  
  # Hybrid search parameters
  k_dense: 50      # Semantic search results
  k_sparse: 50     # BM25 search results
  rrf_k: 60        # Reciprocal Rank Fusion parameter
  fuse_weights:
    dense: 0.7     # Semantic weight
    sparse: 0.3    # BM25 weight
```

- `initial_top_k`: Documents retrieved before reranking
- `final_top_k`: Documents used for response generation
- `enable_reranking`: Whether to use cross-encoder reranking
- `collection_weights`: Priority distribution across document types
- `k_dense/k_sparse`: Results from each search method
- `fuse_weights`: Hybrid search combination weights

## Memory Management

```yaml
memory:
  compression_threshold: 5
```

- `compression_threshold`: Number of messages before triggering conversation compression. When a user has this many unprocessed raw messages, the system automatically compresses older conversations into summaries to manage memory and improve retrieval performance.

## Query Router

```yaml
query_router:
  last_n_messages: 5
  routing_method: 'hybrid'
```

- `last_n_messages`: Conversation context for routing decisions
- `routing_method`: Combines semantic similarity and LLM-based routing

## Reranker

```yaml
reranker:
  model: "xitao/bge-reranker-v2-m3"
  batch_size: 32
  max_candidates_for_rerank: 200
  activation: "sigmoid"
```

- `model`: BGE cross-encoder for relevance scoring
- `batch_size`: Reranking batch size for efficiency
- `max_candidates_for_rerank`: Maximum documents to rerank
- `activation`: Score activation function

## Usage

1. Modify `configs/config.yaml` as needed for your environment
2. Cluster vs local configurations are indicated by comments
3. The system automatically loads configuration on startup
4. Restart services after configuration changes
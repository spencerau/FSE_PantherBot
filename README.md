# FSE_PantherBot

AI-powered academic advising platform for Chapman University's Fowler School of Engineering

## Overview

FSE_PantherBot is a sophisticated RAG (Retrieval-Augmented Generation) system that provides 24/7 academic advising support via the Fowler School of Engineering Slack Workspace. It combines multiple AI technologies to deliver personalized, accurate guidance to undergraduate students using university catalogs and policies.

## Architecture

### Core Components

- **Document Ingestion**: Apache Tika extracts content from PDFs and academic catalogs
- **Embedding Model**: BGE-M3 generates semantic embeddings for documents and queries
- **Vector Database**: Qdrant stores document embeddings with hybrid search capabilities
- **Reranker**: BGE-Reranker-V2-M3 improves retrieval relevance
- **LLM**: GPT-OSS 120B generates final responses via Ollama
- **Memory System**: PostgreSQL stores conversation history with automatic compression

### Retrieval Pipeline

1. **Query Router**: Combines semantic similarity and LLM-based routing to select appropriate document collections
2. **Hybrid Search**: Fuses dense (semantic) and sparse (BM25) retrieval for optimal results
3. **Reranking**: Refines retrieved chunks using cross-encoder model
4. **Response Generation**: LLM synthesizes answers using retrieved context and conversation memory

### Memory Management

- **Conversation Storage**: PostgreSQL tracks user interactions and chat history
- **Memory Compression**: Intermediate LLM summarizes conversations to maintain context while reducing tokens
- **Student Profiles**: Persistent storage of major, catalog year, and academic preferences

## Configuration

All system parameters are configured in `configs/config.yaml`<br>
See [`configs/README.md`](configs/README.md) for detailed options including:

- Model selection and parameters
- Retrieval weights and thresholds  
- Memory compression settings
- Collection-specific configurations

## Usage

### Local Deployment

- needs to be updated

### DGX0 Compute Cluster

```bash
# Sync code to cluster
./scripts/sync_to_cluster.sh

# Deploy on cluster assuming ssh keys are set up properly
ssh dgx0.chapman.edu
./scripts/run_cluster.sh -b -c -f
```

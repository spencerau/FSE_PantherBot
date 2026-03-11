#!/bin/bash

# Local testing script - uses smaller models and local Ollama.
# Sets LOCAL_DEV=true so config.local.yaml + model.local.yaml are loaded.

echo "=== FSE_PantherBot Local Testing Setup ==="
echo

export LOCAL_DEV=true

# Force a safe context window for local embedding runs (bge-m3 only supports 8192)
export OLLAMA_NUM_CTX=8192

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Parse options
BUILD=false
CLEAN=false
INGEST=false

while getopts ":bci" opt; do
  case ${opt} in
    b )
      BUILD=true
      ;;
    c )
      CLEAN=true
      ;;
    i )
      INGEST=true
      ;;
    \? )
      echo "Usage: $0 [-b] [-c] [-i]"
      echo "  -b  Rebuild Docker image"
      echo "  -c  Clean Qdrant data"
      echo "  -i  Run ingestion after starting services"
      exit 1
      ;;
  esac
done

# Build image if requested
if [ "$BUILD" = true ]; then
    echo "Building Docker image..."
    docker compose build
    echo
fi

# Clean Qdrant data if requested
if [ "$CLEAN" = true ]; then
    echo "Cleaning Qdrant data..."
    rm -rf qdrant_data/*
    echo "Qdrant data cleaned"
    echo
fi

# Check if native Ollama is running (required for Mac GPU acceleration)
echo "Checking native Ollama (required for Mac GPU)..."
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "Native Ollama is not running. Starting Ollama..."
    open -a Ollama
    echo "Waiting for Ollama to start..."
    sleep 5
    
    # Check again
    if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "ERROR: Failed to start Ollama"
        echo "Please ensure Ollama is installed: https://ollama.ai/download"
        exit 1
    fi
fi
echo "Native Ollama is running"

# Start core services (qdrant, tika only - no Docker ollama)
echo
echo "Starting services (Qdrant, Tika)..."
docker compose up -d qdrant tika

echo
echo "Waiting for services to be ready..."
sleep 5

# Check Qdrant
echo -n "  Checking Qdrant... "
if curl -s http://localhost:6333/healthz >/dev/null 2>&1; then
    echo "OK"
else
    echo "FAILED - Failed to connect to Qdrant"
    exit 1
fi

# Check Tika
echo -n "  Checking Tika... "
if curl -s http://localhost:9998/tika >/dev/null 2>&1; then
    echo "OK"
else
    echo "FAILED - Failed to connect to Tika"
    exit 1
fi

echo
echo "Pulling required models to native Ollama..."

# Pull embedding model
echo "  Pulling bge-m3:567m (embedding)..."
ollama pull bge-m3:567m


# Pull main LLM
echo "  Pulling gemma3:4b (main LLM)..."
ollama pull gemma3:4b

# Pull router LLM
echo "  Pulling gemma3:1b (query router)..."
ollama pull gemma3:1b

echo "  Pulling xitao/bge-reranker-v2-m3 (reranker..."
ollama pull xitao/bge-reranker-v2-m3

echo
echo "All models ready!"

# Run ingestion if requested
if [ "$INGEST" = true ]; then
    echo
    echo "Running ingestion with local config..."
    source .venv/bin/activate
    LOCAL_DEV=true PYTHONPATH=src python3 src/ingestion/ingest.py
    echo
fi

# Start Streamlit
echo
echo "Starting Streamlit UI..."
docker compose up -d streamlit

echo
echo "Local testing environment ready!"
echo
echo "Available services:"
echo "   Streamlit UI:     http://localhost:8501"
echo "   Qdrant Dashboard: http://localhost:6333/dashboard"
echo "   Tika:             http://localhost:9998"
echo "   Ollama (native):  http://localhost:11434"
echo
echo "To run ingestion manually:"
echo "   source .venv/bin/activate"
echo "   LOCAL_DEV=true PYTHONPATH=src python3 src/ingestion/ingest.py"
echo
echo "To stop Docker services:"
echo "   docker compose down"
echo
echo "Note: Native Ollama must remain running for GPU acceleration"

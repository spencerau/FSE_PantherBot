#!/bin/bash

# Run data ingestion against DGX cluster (default) or local Ollama.
# Cluster mode uses model.yaml (DGX ports/models). Local mode adds .local.yaml overrides.
#
# Usage: ./scripts/ingest.sh [--local|-l] [--clean|-c]

set -e

MODE="cluster"
CLEAN=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --local|-l)
      MODE="local"
      shift
      ;;
    --clean|-c)
      CLEAN=true
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--local|-l] [--clean|-c]"
      echo "  --local, -l   Use local Ollama (loads config.local.yaml + model.local.yaml)"
      echo "  --clean, -c   Wipe Qdrant data before ingesting"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Run '$0 --help' for usage."
      exit 1
      ;;
  esac
done

echo "=== FSE PantherBot Ingestion ==="
echo "Mode: $MODE"
echo

if [ "$CLEAN" = true ]; then
  echo "Stopping Qdrant..."
  docker compose stop qdrant
  echo "Wiping Qdrant data..."
  sudo rm -rf qdrant_data/*
  echo "Restarting Qdrant..."
  docker compose up -d qdrant
  echo -n "Waiting for Qdrant to be ready..."
  for i in $(seq 1 20); do
    if curl -s http://localhost:6333/healthz >/dev/null 2>&1; then
      echo " OK"
      break
    fi
    echo -n "."
    sleep 1
  done
  echo
fi

echo -n "Checking Qdrant (localhost:6333)... "
if ! curl -s http://localhost:6333/healthz >/dev/null 2>&1; then
  echo "FAILED"
  echo "Start it with: docker compose up -d qdrant"
  exit 1
fi
echo "OK"

if [ "$MODE" = "cluster" ]; then
  echo -n "Checking DGX tunnel (localhost:10001)... "
  if ! nc -z localhost 10001 >/dev/null 2>&1; then
    echo "FAILED"
    echo "Start SSH tunnel: ssh -L 10001:localhost:10001 -L 10002:localhost:10002 spau@dgx_cluster"
    exit 1
  fi
  echo "OK"
  echo
  echo "Running ingestion (cluster mode - DGX models + ports, no local config overrides)..."
  PYTHONPATH=src .venv/bin/python src/ingestion/ingest.py
else
  echo
  echo "Running ingestion (local mode - local Ollama, .local.yaml overrides active)..."
  LOCAL_DEV=true PYTHONPATH=src .venv/bin/python src/ingestion/ingest.py
fi

echo
echo "Ingestion complete!"

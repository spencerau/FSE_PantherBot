#!/bin/bash

BUILD=false
RUN_TESTS=false
CLEAN_COLLECTIONS=false

while getopts ":btc" opt; do
  case ${opt} in
    b )
      BUILD=true
      ;;
    t )
      RUN_TESTS=true
      ;;
    c )
      CLEAN_COLLECTIONS=true
      ;;
    \? )
      echo "Usage: $0 [-b] [-t] [-c]"
      echo "  -b  Rebuild containers"
      echo "  -t  Run tests after starting services"
      echo "  -c  Clean Qdrant collections and run ingestion"
      echo ""
      echo "Examples:"
      echo "  ./run.sh           # Start services only (no rebuild, no ingestion)"
      echo "  ./run.sh -c        # Clean collections and run ingestion"
      echo "  ./run.sh -b        # Rebuild containers and start services"
      echo "  ./run.sh -c -b -t  # Clean, rebuild, run ingestion, and test"
      exit 1
      ;;
  esac
done

clear

echo "Stopping any running containers..."
docker compose down

export PYTHONPATH="$PYTHONPATH:$(pwd)/src"

if [ "$CLEAN_COLLECTIONS" = true ]; then
  echo "Cleaning all Qdrant collections..."
  echo "Removing qdrant_data directory..."
  sudo rm -rf qdrant_data
  echo "Collection cleanup completed."
fi

echo "Starting containers..."
if [ "$BUILD" = true ]; then
  echo "Building and starting containers..."
  docker compose up -d --build
else
  echo "Starting containers without rebuild..."
  docker compose up -d
fi

echo "Waiting for containers to be ready..."
sleep 5

# Only run ingestion if CLEAN_COLLECTIONS flag is set
if [ "$CLEAN_COLLECTIONS" = true ]; then
  echo "Ingesting data from PDF documents..."
  python src/ingestion/ingest.py
else
  echo "Skipping ingestion (use -c flag to clean collections and run ingestion)"
fi

echo "Running tests..."
if [ "$RUN_TESTS" = true ]; then
  pytest -s tests/ -v
  echo "Tests completed"

  echo "cleaning up..."
  rm -rf qdrant_data/collections/test*
else
  echo "Tests skipped."
fi


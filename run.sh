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
      echo "  -b  Enable rebuild of containers"
      echo "  -t  Run tests after starting services"
      echo "  -c  Clean all Qdrant collections before ingestion"
      echo ""
      echo "Examples:"
      echo "  ./run.sh           # Normal run with ingestion"
      echo "  ./run.sh -c        # Clean collections and run with ingestion"
      echo "  ./run.sh -b        # Rebuild containers and run"
      echo "  ./run.sh -c -b -t  # Clean, rebuild, run, and test"
      exit 1
      ;;
  esac
done

clear

echo "Stopping any running containers..."
docker compose down

export PYTHONPATH="$PYTHONPATH:$(pwd)/src"

# Clean collections if requested (do this before starting containers)
if [ "$CLEAN_COLLECTIONS" = true ]; then
  echo "Cleaning all Qdrant collections..."
  echo "Removing qdrant_data directory..."
  sudo rm -rf qdrant_data
  echo "Collection cleanup completed."
fi

echo "Starting containers..."
if [ "$BUILD" = true ] || [ "$CLEAN_COLLECTIONS" = true ]; then
  echo "Building and starting containers..."
  docker compose up -d --build
else
  echo "Starting containers without rebuild..."
  docker compose up -d
fi

#echo "Pulling required models..."
#./pull_models_mac.sh

echo "Waiting for containers to be ready..."
sleep 5

# echo "Checking if Qdrant is responding..."
# curl -f http://localhost:6333/collections || echo "Qdrant not yet ready, waiting longer..."
# sleep 10

echo "Ingesting data from PDF documents..."
python src/ingestion/ingest.py

# echo "Checking collections after ingestion..."
# curl http://localhost:6333/collections

echo "Running tests..."
if [ "$RUN_TESTS" = true ]; then
  pytest -s tests/ -v
  echo "Tests completed"

  echo "cleaning up..."
  rm -rf qdrant_data/collections/test*
else
  echo "Tests skipped."
fi


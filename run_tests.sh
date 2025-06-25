#!/bin/bash

# Default build flag is false (no build)
BUILD=false

# Parse command line arguments
while getopts ":b" opt; do
  case ${opt} in
    b )
      BUILD=true
      ;;
    \? )
      echo "Usage: $0 [-b]"
      echo "  -b  Enable rebuild of containers"
      exit 1
      ;;
  esac
done

clear

echo "Stopping any running containers..."
docker compose down

echo "Starting containers..."
if [ "$BUILD" = true ]; then
  echo "Building and starting containers..."
  docker compose up -d --build
else
  echo "Starting containers without rebuild..."
  docker compose up -d
fi

#echo "Pulling required models..."
#./pull_models_mac.sh

echo "Running tests..."
python -m pytest tests/test_qdrant_ingest.py -v

echo "Tests completed"


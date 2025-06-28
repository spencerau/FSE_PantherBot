#!/bin/bash

BUILD=false

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
export PYTHONPATH="$PYTHONPATH:$(pwd)/src"
# pytest -s tests/test_ingestion.py -v

# python -m pytest tests/test_ingestion.py -v

pytest -s tests/ -v

echo "Tests completed"


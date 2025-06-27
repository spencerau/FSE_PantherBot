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

# # Check for tika-server.jar
# if [ ! -f ./dependencies/tika-server.jar ]; then
#   echo "ERROR: tika-server.jar is missing from ./dependencies. Please download it before running tests."
#   exit 1
# fi

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
python -m pytest tests/test_ingestion.py -v

echo "Tests completed"


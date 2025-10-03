#!/bin/bash

BUILD=false
RUN_TESTS=false
CLEAN_COLLECTIONS=false
CLEAN_MEMORY=false

while getopts ":btcm" opt; do
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
    m )
      CLEAN_MEMORY=true
      ;;
    \? )
      echo "Usage: $0 [-b] [-t] [-c] [-m]"
      echo "  -b  Rebuild containers"
      echo "  -t  Run tests after starting services"
      echo "  -c  Clean Qdrant collections and run ingestion"
      echo "  -m  Clean Postgres memory database"
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

if [ "$CLEAN_MEMORY" = true ]; then
  echo "Cleaning Postgres memory database..."
  echo "Removing postgres_data directory..."
  sudo rm -rf postgres_data
  echo "Memory database cleanup completed."
fi

echo "Starting containers..."
if [ "$BUILD" = true ]; then
  echo "Building and starting containers..."
  docker compose up -d --build
  DC_EXIT=$?
  if [ $DC_EXIT -ne 0 ]; then
    echo "docker compose up (with build) failed with exit code $DC_EXIT. Aborting further steps."
    echo "Check the docker build logs and available disk space. Example commands to investigate:"
    echo "  docker compose logs --no-color --tail=200"
    echo "  docker system df"
    exit $DC_EXIT
  fi
else
  echo "Starting containers without rebuild..."
  docker compose up -d
  DC_EXIT=$?
  if [ $DC_EXIT -ne 0 ]; then
    echo "docker compose up failed with exit code $DC_EXIT. Aborting further steps."
    echo "Check the docker logs and status. Example commands to investigate:"
    echo "  docker compose logs --no-color --tail=200"
    exit $DC_EXIT
  fi
fi

echo "Waiting for containers to be ready..."

# Helper: wait for a host:port to accept TCP connections
wait_for_service() {
  local host="$1"; local port="$2"; local timeout="${3:-60}"
  echo "Waiting for $host:$port to be ready (timeout ${timeout}s) ..."
  for i in $(seq 1 $timeout); do
    # Use nc (netcat) to test connection, fallback to curl if nc unavailable
    if command -v nc >/dev/null 2>&1; then
      if nc -z "$host" "$port" >/dev/null 2>&1; then
        echo "$host:$port is available"
        return 0
      fi
    elif command -v curl >/dev/null 2>&1; then
      if curl -s --connect-timeout 1 "http://$host:$port" >/dev/null 2>&1; then
        echo "$host:$port is available"
        return 0
      fi
    else
      # Fallback to /dev/tcp if available
      if (echo > /dev/tcp/${host}/${port}) >/dev/null 2>&1; then
        echo "$host:$port is available"
        return 0
      fi
    fi
    sleep 1
  done
  echo "Timed out waiting for $host:$port after ${timeout}s"
  return 1
}

# Wait for Qdrant (exposed on localhost:6333) and Postgres (localhost:5432)
wait_for_service "localhost" 6333 60
QDRANT_OK=$?
wait_for_service "localhost" 5432 60
PG_OK=$?

# Only run ingestion if CLEAN_COLLECTIONS flag is set and Qdrant is reachable
if [ "$CLEAN_COLLECTIONS" = true ]; then
  if [ $QDRANT_OK -ne 0 ]; then
    echo "Qdrant not available; skipping ingestion. Start the services and try again."
    echo "You can retry ingestion later with: python src/ingestion/ingest.py"
  else
    echo "Ingesting data from PDF documents..."
    # Use virtual environment if available, otherwise system python
    if [ -f ".venv/bin/python" ]; then
      .venv/bin/python src/ingestion/ingest.py
    elif [ -f "venv/bin/python" ]; then
      venv/bin/python src/ingestion/ingest.py
    else
      python src/ingestion/ingest.py
    fi
    INGEST_EXIT=$?
    if [ $INGEST_EXIT -ne 0 ]; then
      echo "Ingestion failed with exit code $INGEST_EXIT"
      echo "Check the ingestion logs above for errors."
    else
      echo "Ingestion completed successfully"
    fi
  fi
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


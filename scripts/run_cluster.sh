#!/bin/bash

# Cluster-specific run script (no docke# Check if Ollama is accessible
echo "Checking Ollama connectivity..."

# Ensure ollama-spencerau container is running with proper port mapping
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Ollama not accessible on localhost:11434, checking container..."
  
  if docker ps | grep -q "spencerau-ollama"; then
    echo "spencerau-ollama is running but not exposing port 11434"
    echo "Stopping container to restart with port mapping..."
    docker stop spencerau-ollama
  fi
  
  echo "Starting spencerau-ollama with port mapping..."

# --gpus all \ is for using all GPUs
# --gpus device=7 \ is for using specific GPU (e.g., GPU 7)
# --gpus 1 \ is for using one GPU (docker will choose automatically)

  docker run -d \
    --name spencerau-ollama \
    --runtime=nvidia \
    --gpus 1 \
    -p 11434:11434 \
    -e OLLAMA_MODELS=/app/rundir/ollama_models \
    -e NVIDIA_VISIBLE_DEVICES=all \
    -e NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    -v /nfshome/spau/ollama_rundir:/app/rundir \
    -v /nfshome/spau/ollama_models:/app/rundir/ollama_models \
    ollama/ollama serve
  
  echo "Waiting for Ollama to start..."
  sleep 10
  
  # Check again
  if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "ERROR: Ollama still not accessible at localhost:11434"
    echo "Please check spencerau-ollama container:"
    echo "  docker logs spencerau-ollama"
    exit 1
  fi
fi

echo "Ollama is accessible"
# This mimics what docker-compose.yml does with plain Docker commands

BUILD=false
CLEAN_COLLECTIONS=false
CLEAN_MEMORY=false
FULL_SERVICES=false

while getopts ":bcmf" opt; do
  case ${opt} in
    b )
      BUILD=true
      ;;
    c )
      CLEAN_COLLECTIONS=true
      ;;
    m )
      CLEAN_MEMORY=true
      ;;
    f )
      FULL_SERVICES=true
      ;;
    \? )
      echo "Usage: $0 [-b] [-c] [-m] [-f]"
      echo "  -b  Rebuild containers"
      echo "  -c  Clean Qdrant collections and run ingestion"
      echo "  -m  Clean Postgres memory database"
      echo "  -f  Start full services (Slack bot, memory compressor)"
      exit 1
      ;;
  esac
done

echo "Starting FSE_PantherBot on cluster..."

# Note: Using host networking to connect to existing ollama-spencerau container

# Stop and remove existing containers
echo "Cleaning up existing containers..."
docker stop spencerau-qdrant spencerau-postgres spencerau-tika spencerau-streamlit spencerau-slack-bot spencerau-memory-compressor 2>/dev/null || true
docker rm spencerau-qdrant spencerau-postgres spencerau-tika spencerau-streamlit spencerau-slack-bot spencerau-memory-compressor 2>/dev/null || true

if [ "$CLEAN_COLLECTIONS" = true ]; then
  echo "Cleaning Qdrant data..."
  if [ -d "qdrant_data" ]; then
    docker run --rm -v "$(pwd)/qdrant_data:/data" alpine:latest sh -c "rm -rf /data/*"
    echo "Qdrant data cleaned"
  fi
fi

if [ "$CLEAN_MEMORY" = true ]; then
  echo "Cleaning Postgres data..."
  if [ -d "postgres_data" ]; then
    docker run --rm -v "$(pwd)/postgres_data:/data" alpine:latest sh -c "rm -rf /data/*"
    echo "Postgres data cleaned"
  fi
fi

# Start Qdrant
echo "Starting Qdrant..."
docker run -d \
  --name spencerau-qdrant \
  --network host \
  -v $(pwd)/qdrant_data:/qdrant/storage \
  qdrant/qdrant

# Load environment variables from memory .env file
if [ -f "src/memory/.env" ]; then
  echo "Loading database configuration from src/memory/.env..."
  set -a  # automatically export all variables
  source src/memory/.env
  set +a  # stop automatically exporting
else
  echo "WARNING: src/memory/.env not found, using default database credentials"
  export POSTGRES_USER=pantherbot
  export POSTGRES_PASSWORD=pantherbot
  export POSTGRES_DB=pantherbot
fi

# Start Postgres
echo "Starting Postgres..."
docker run -d \
  --name spencerau-postgres \
  --network host \
  -v $(pwd)/postgres_data:/var/lib/postgresql/data \
  -e POSTGRES_USER=${POSTGRES_USER} \
  -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD} \
  -e POSTGRES_DB=${POSTGRES_DB} \
  postgres:15

# Start Tika
echo "Starting Tika..."
docker run -d \
  --name spencerau-tika \
  --network host \
  apache/tika:latest

# Build app container if requested
if [ "$BUILD" = true ]; then
  echo "Building FSE_PantherBot container..."
  docker build -t fse_pantherbot .
fi

# Wait for services to be ready
echo "Waiting for services to start..."
sleep 10

# Wait for Postgres to be ready
echo "Waiting for Postgres to be ready..."
for i in {1..10}; do
  if PGPASSWORD=${POSTGRES_PASSWORD} psql -h localhost -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "SELECT 1;" >/dev/null 2>&1; then
    echo "Postgres is ready"
    break
  fi
  sleep 1
done

# Wait for Qdrant to be ready
echo "Waiting for Qdrant to be ready..."
for i in {1..10}; do
  if curl -s http://localhost:6333/health >/dev/null 2>&1; then
    echo "Qdrant is ready"
    break
  fi
  sleep 1
done

# Check if Qdrant is accessible
if ! curl -s http://localhost:6333/health >/dev/null 2>&1; then
  echo "ERROR: Qdrant is not accessible at localhost:6333"
  echo "Please check if Qdrant container is running properly"
  exit 1
fi

# Check if Ollama is accessible and pull required models
echo "Checking Ollama accessibility..."
if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Ollama is accessible, checking models..."
  
  # Check if embedding model exists, pull if needed
  if ! curl -s http://localhost:11434/api/tags | grep -q "bge-m3:567m"; then
    echo "Pulling embedding model bge-m3:567m..."
    curl -X POST http://localhost:11434/api/pull -d '{"name": "bge-m3:567m"}' >/dev/null 2>&1 &
  fi
  
  # Check if reranker model exists, pull if needed  
  if ! curl -s http://localhost:11434/api/tags | grep -q "xitao/bge-reranker-v2-m3"; then
    echo "Pulling reranker model xitao/bge-reranker-v2-m3..."
    curl -X POST http://localhost:11434/api/pull -d '{"name": "xitao/bge-reranker-v2-m3"}' >/dev/null 2>&1 &
  fi
  
  # Check if LLM model exists, pull if needed
  if ! curl -s http://localhost:11434/api/tags | grep -q "deepseek-r1:70b"; then
    echo "Pulling LLM model deepseek-r1:70b..."
    curl -X POST http://localhost:11434/api/pull -d '{"name": "deepseek-r1:70b"}' >/dev/null 2>&1 &
  fi
  
  echo "Model checks/pulls initiated..."
  sleep 5
else
  echo "WARNING: Ollama not accessible at localhost:11434"
  echo "You may need to start Ollama manually:"
  echo "  docker exec -it ollama-spencerau ollama serve"
fi

# Run ingestion if cleaning collections
if [ "$CLEAN_COLLECTIONS" = true ]; then
  echo "Running ingestion..."
  docker run --rm \
    --network host \
    -v $(pwd)/src:/app/src \
    -v $(pwd)/configs:/app/configs \
    -v $(pwd)/data:/app/data \
    -e QDRANT_HOST=localhost \
    -e OLLAMA_HOST=localhost \
    -e TIKA_SERVER_ENDPOINT=http://localhost:9998 \
    -e PYTHONPATH=/app/src \
    fse_pantherbot \
    python src/ingestion/ingest.py
fi

# Start Streamlit app
echo "Starting Streamlit app..."
docker run -d \
  --name spencerau-streamlit \
  --network host \
  -v $(pwd)/src:/app/src \
  -v $(pwd)/configs:/app/configs \
  -v $(pwd)/data:/app/data \
  -e QDRANT_HOST=localhost \
  -e OLLAMA_HOST=localhost \
  -e TIKA_SERVER_ENDPOINT=http://localhost:9998 \
  -e PYTHONPATH=/app/src \
  fse_pantherbot

# Check if Slack environment file exists before starting Slack bot
if [ "$FULL_SERVICES" = true ] && [ -f "src/slack/.env" ]; then
  echo "Starting Slack bot..."
  # Verify that memory .env is also available for database connection
  if [ ! -f "src/memory/.env" ]; then
    echo "WARNING: src/memory/.env not found but required for Slack bot database connection"
  fi
  docker run -d \
    --name spencerau-slack-bot \
    --network host \
    --env-file src/slack/.env \
    --env-file src/memory/.env \
    -v $(pwd)/src:/app/src \
    -v $(pwd)/configs:/app/configs \
    -v $(pwd)/data:/app/data \
    -e QDRANT_HOST=localhost \
    -e OLLAMA_HOST=localhost \
    -e POSTGRES_HOST=localhost \
    -e RERANK_DISABLED=true \
    -e PYTHONPATH=/app/src \
    fse_pantherbot \
    python src/slack/bot.py
elif [ "$FULL_SERVICES" = true ]; then
  echo "Slack .env file not found, skipping Slack bot..."
fi

# Check if memory environment file exists before starting memory compressor
if [ "$FULL_SERVICES" = true ] && [ -f "src/memory/.env" ]; then
  echo "Starting memory compressor..."
  docker run -d \
    --name spencerau-memory-compressor \
    --network host \
    --env-file src/memory/.env \
    -v $(pwd)/src:/app/src \
    -v $(pwd)/configs:/app/configs \
    -v $(pwd)/scripts:/app/scripts \
    -e OLLAMA_HOST=localhost \
    -e POSTGRES_HOST=localhost \
    -e PYTHONPATH=/app/src \
    fse_pantherbot \
    bash scripts/memory_compression.sh
elif [ "$FULL_SERVICES" = true ]; then
  echo "Memory .env file not found, skipping memory compressor..."
fi

echo "FSE_PantherBot started!"
echo ""
echo "Services running:"
echo "- Qdrant: http://localhost:6333"
echo "- Streamlit: http://localhost:8501"
echo "- Postgres: localhost:5432"
echo "- Tika: http://localhost:9998"
if [ "$FULL_SERVICES" = true ] && [ -f "src/slack/.env" ]; then
  echo "- Slack Bot: Running"
fi
if [ "$FULL_SERVICES" = true ] && [ -f "src/memory/.env" ]; then
  echo "- Memory Compressor: Running"
fi
echo ""
echo "Create SSH tunnel: "
echo "ssh -L 8501:localhost:8501 -L 6333:localhost:6333 -L 5432:localhost:5432 spau@dgx0.chapman.edu"
echo "Then visit: http://localhost:8501"
echo ""
echo "To check container status: docker ps | grep spencerau"
echo "To view logs: docker logs spencerau-<service-name>"
echo "To stop all services: docker stop \$(docker ps -q --filter name=spencerau)"

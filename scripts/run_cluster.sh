#!/bin/bash

# Cluster-specific run script (no docke# Check if main Ollama is accessible
echo "Checking main Ollama connectivity..."

# Ensure spencerau-ollama container is running with proper port mapping
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Main Ollama not accessible on localhost:11434, checking container..."
  
  if docker ps | grep -q "spencerau-ollama"; then
    echo "spencerau-ollama is running but not exposing port 11434"
    echo "Stopping container to restart with port mapping..."
    docker stop spencerau-ollama
  fi
  
  echo "Starting spencerau-ollama (main LLM) with port mapping..."

# GPU Configuration:
# --gpus all              - Use all available GPUs
# --gpus '"device=0,1"'   - Use specific GPUs (e.g., GPU 0 and 1)
# --gpus '"device=7"'     - Use single specific GPU (e.g., GPU 7)
# --gpus 1                - Use one GPU (docker will choose automatically)

  docker run -d \
    --name spencerau-ollama \
    --gpus '"device=7"' \
    -p 11434:11434 \
    -e NVIDIA_VISIBLE_DEVICES=7 \
    -e NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    -e OLLAMA_MODELS=/app/rundir/ollama_models \
    -v /nfshome/spau/ollama_rundir:/app/rundir \
    ollama/ollama:latest serve
  
  echo "Waiting for main Ollama to start..."
  sleep 10
  
  # Check again
  if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "ERROR: Main Ollama still not accessible at localhost:11434"
    echo "Please check spencerau-ollama container:"
    echo "  docker logs spencerau-ollama"
    exit 1
  fi
fi

echo "Main Ollama is accessible"

# Check if intermediate LLM is accessible
echo "Checking intermediate LLM connectivity..."

if ! curl -s http://localhost:11435/api/tags >/dev/null 2>&1; then
  echo "Intermediate LLM not accessible on localhost:11435, checking container..."
  
  if docker ps | grep -q "spencerau-intermediate-llm"; then
    echo "spencerau-intermediate-llm is running but not exposing port 11435"
    echo "Stopping container to restart with port mapping..."
    docker stop spencerau-intermediate-llm
  fi
  
  echo "Starting spencerau-intermediate-llm (routing/compression) with port mapping..."

  docker run -d \
    --name spencerau-intermediate-llm \
    --gpus '"device=6"' \
    -p 11435:11434 \
    -e NVIDIA_VISIBLE_DEVICES=6 \
    -e NVIDIA_DRIVER_CAPABILITIES=compute,utility \
    -e OLLAMA_MODELS=/app/rundir/ollama_models \
    -v /nfshome/spau/ollama_rundir:/app/rundir \
    ollama/ollama:latest serve
  
  echo "Waiting for intermediate LLM to start..."
  sleep 10
  
  # Check again
  if ! curl -s http://localhost:11435/api/tags >/dev/null 2>&1; then
    echo "ERROR: Intermediate LLM still not accessible at localhost:11435"
    echo "Please check spencerau-intermediate-llm container:"
    echo "  docker logs spencerau-intermediate-llm"
    exit 1
  fi
fi

echo "Intermediate LLM is accessible"
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

# Stop and remove existing containers (but not Ollama containers - they persist)
echo "Cleaning up existing containers..."
docker stop spencerau-qdrant spencerau-postgres spencerau-tika spencerau-streamlit spencerau-slack-bot 2>/dev/null || true
docker rm spencerau-qdrant spencerau-postgres spencerau-tika spencerau-streamlit spencerau-slack-bot 2>/dev/null || true

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
  
  # Check if main LLM model exists, pull if needed
  if ! curl -s http://localhost:11434/api/tags | grep -q "gpt-oss:120b"; then
    echo "Pulling main LLM model gpt-oss:120b..."
    curl -X POST http://localhost:11434/api/pull -d '{"name": "gpt-oss:120b"}' >/dev/null 2>&1 &
  fi
  
  echo "Main Ollama model checks/pulls initiated..."
  sleep 5
else
  echo "WARNING: Main Ollama not accessible at localhost:11434"
  echo "You may need to start Ollama manually:"
  echo "  docker exec -it spencerau-ollama ollama serve"
fi

# Check intermediate LLM and pull required models
echo "Checking intermediate LLM models..."
if curl -s http://localhost:11435/api/tags >/dev/null 2>&1; then
  # Check if router/compression model exists, pull if needed
  if ! curl -s http://localhost:11435/api/tags | grep -q "gpt-oss:20b"; then
    echo "Pulling intermediate LLM model gpt-oss:20b..."
    curl -X POST http://localhost:11435/api/pull -d '{"name": "gpt-oss:20b"}' >/dev/null 2>&1 &
  fi
  
  echo "Intermediate LLM model checks/pulls initiated..."
  sleep 5
else
  echo "WARNING: Intermediate LLM not accessible at localhost:11435"
  echo "You may need to start it manually:"
  echo "  docker exec -it spencerau-intermediate-llm ollama serve"
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
  -e OLLAMA_INTERMEDIATE_HOST=localhost \
  -e OLLAMA_INTERMEDIATE_PORT=11435 \
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
    -e OLLAMA_INTERMEDIATE_HOST=localhost \
    -e OLLAMA_INTERMEDIATE_PORT=11435 \
    -e POSTGRES_HOST=localhost \
    -e RERANK_DISABLED=true \
    -e PYTHONPATH=/app/src \
    fse_pantherbot \
    python src/slack/bot.py
elif [ "$FULL_SERVICES" = true ]; then
  echo "Slack .env file not found, skipping Slack bot..."
fi

# Memory compression is now handled by intermediate LLM (no separate container needed)
# The intermediate LLM at localhost:11435 handles:
#   - Query routing
#   - Dynamic token allocation  
#   - Memory compression
echo "Note: Memory compression uses intermediate LLM at localhost:11435"

echo "FSE_PantherBot started!"
echo ""
echo "Services running:"
echo "- Main Ollama (gpt-oss:120b): http://localhost:11434"
echo "- Intermediate LLM (gpt-oss:20b): http://localhost:11435"
echo "- Qdrant: http://localhost:6333"
echo "- Streamlit: http://localhost:8501"
echo "- Postgres: localhost:5432"
echo "- Tika: http://localhost:9998"
if [ "$FULL_SERVICES" = true ] && [ -f "src/slack/.env" ]; then
  echo "- Slack Bot: Running"
fi
echo ""
echo "Create SSH tunnel: "
echo "ssh -L 8501:localhost:8501 -L 6333:localhost:6333 -L 5432:localhost:5432 -L 11434:localhost:11434 -L 11435:localhost:11435 spau@dgx0.chapman.edu"
echo "Then visit: http://localhost:8501"
echo ""
echo "To check container status: docker ps | grep spencerau"
echo "To view logs: docker logs spencerau-<service-name>"
echo "To stop all services: docker stop \$(docker ps -q --filter name=spencerau)"

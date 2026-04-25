#!/bin/bash
# Start all DGX services (simulates docker-compose for the cluster).
# Starts Docker containers for Qdrant + PostgreSQL, and vLLM processes for
# primary LLM (35B), intermediate LLM (4B), and embedding model.
#
# Usage: ./scripts/dgx_up.sh [--clean] [--ingest]
#   --clean    Wipe Qdrant and Postgres data volumes before starting
#   --ingest   Run ingestion after services are up

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CLEAN=false
INGEST=false

# ---- Configurable ----
QDRANT_CONTAINER="pantherbot-qdrant"
POSTGRES_CONTAINER="pantherbot-postgres"
VLLM_PRIMARY_CONTAINER="pantherbot-vllm-primary"
VLLM_INTERMEDIATE_CONTAINER="pantherbot-vllm-intermediate"
VLLM_EMBEDDING_CONTAINER="pantherbot-vllm-embedding"
VLLM_IMAGE="vllm/vllm-openai:latest"

QDRANT_PORT="${QDRANT_PORT:-10004}"
POSTGRES_PORT="${POSTGRES_PORT:-10005}"

QDRANT_DATA="$REPO_DIR/qdrant_data"
POSTGRES_DATA="$REPO_DIR/postgres_data"

LLM_MODEL="Qwen/Qwen3.6-35B-A3B"
INTERMEDIATE_MODEL="Qwen/Qwen3.5-4B"
EMBEDDING_MODEL="Qwen/Qwen3-Embedding-8B"

LLM_PORT=10001
INTERMEDIATE_PORT=10002
EMBEDDING_PORT=10003

LLM_GPUS="3"
LLM_TP=1                  # tensor parallel size — must match number of GPUs above
INTERMEDIATE_GPUS="0"
INTERMEDIATE_TP=1
EMBEDDING_GPUS="0"

# vLLM tuning
LLM_GPU_MEM_UTIL="0.90"
INTERMEDIATE_GPU_MEM_UTIL="0.4"
EMBEDDING_GPU_MEM_UTIL="0.3"
LLM_MAX_MODEL_LEN=65536        # cap below 128K to leave room for KV cache on shared GPU
INTERMEDIATE_MAX_MODEL_LEN=16000
EMBEDDING_MAX_MODEL_LEN=32768

# Must match src/fse_memory/.env
POSTGRES_DB="${POSTGRES_DB:-pantherbot}"
POSTGRES_USER="${POSTGRES_USER:-pantherbot}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-pantherbot}"
# ----------------------

while [[ $# -gt 0 ]]; do
  case $1 in
    --clean|-c) CLEAN=true; shift ;;
    --ingest|-i) INGEST=true; shift ;;
    --help|-h)
      echo "Usage: $0 [--clean] [--ingest]"
      echo "  --clean    Wipe Qdrant and Postgres data before starting"
      echo "  --ingest   Run ingestion after services are up"
      exit 0 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

cd "$REPO_DIR"

wait_for_http() {
  local url="$1" name="${2:-$url}" timeout="${3:-120}"
  echo -n "  Waiting for $name..."
  for i in $(seq 1 $timeout); do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo " ready"
      return 0
    fi
    sleep 2
  done
  echo " TIMED OUT after $((timeout * 2))s"
  return 1
}

# ============================================================
# 1. Optionally clean data volumes
# ============================================================
if [ "$CLEAN" = true ]; then
  echo "=== Cleaning data volumes ==="
  docker stop "$QDRANT_CONTAINER" "$POSTGRES_CONTAINER" \
    "$VLLM_PRIMARY_CONTAINER" "$VLLM_INTERMEDIATE_CONTAINER" "$VLLM_EMBEDDING_CONTAINER" \
    2>/dev/null || true
  docker rm "$QDRANT_CONTAINER" "$POSTGRES_CONTAINER" \
    "$VLLM_PRIMARY_CONTAINER" "$VLLM_INTERMEDIATE_CONTAINER" "$VLLM_EMBEDDING_CONTAINER" \
    2>/dev/null || true
  docker run --rm -v "$REPO_DIR:/app" alpine sh -c "rm -rf /app/qdrant_data /app/postgres_data"
  echo "Data volumes removed."
fi

# ============================================================
# 2. Qdrant
# ============================================================
echo ""
echo "=== Qdrant ==="
if docker ps -q -f name="$QDRANT_CONTAINER" | grep -q .; then
  echo "  Already running."
else
  docker rm -f "$QDRANT_CONTAINER" 2>/dev/null || true
  mkdir -p "$QDRANT_DATA"
  docker run -d \
    --name "$QDRANT_CONTAINER" \
    --restart unless-stopped \
    --network=host \
    -e QDRANT__SERVICE__HTTP_PORT="$QDRANT_PORT" \
    -v "$QDRANT_DATA:/qdrant/storage" \
    qdrant/qdrant:latest
  echo "  Started."
fi

# ============================================================
# 3. PostgreSQL
# ============================================================
echo ""
echo "=== PostgreSQL ==="
if docker ps -q -f name="$POSTGRES_CONTAINER" | grep -q .; then
  echo "  Already running."
else
  docker rm -f "$POSTGRES_CONTAINER" 2>/dev/null || true
  mkdir -p "$POSTGRES_DATA"
  docker run -d \
    --name "$POSTGRES_CONTAINER" \
    --restart unless-stopped \
    --network=host \
    -e PGPORT="$POSTGRES_PORT" \
    -e POSTGRES_DB="$POSTGRES_DB" \
    -e POSTGRES_USER="$POSTGRES_USER" \
    -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
    -v "$POSTGRES_DATA:/var/lib/postgresql/data" \
    postgres:16
  echo "  Started."
fi

# ============================================================
# 4. Wait for Docker services and init DB
# ============================================================
wait_for_http "http://localhost:$QDRANT_PORT/healthz" "Qdrant" 60
wait_for_http "http://localhost:$POSTGRES_PORT" "PostgreSQL" 30 2>/dev/null || true

echo ""
echo "=== Database schema init: run manually from inside your app container ==="
echo "  docker run -it --rm --network=host -v \"\$PWD:/app\" -w /app python:3.12 bash"
echo "  pip install -e . && PYTHONPATH=src python scripts/init_db.py"

# ============================================================
# 5. vLLM: embedding model
# ============================================================
echo ""
echo "=== vLLM: embedding ($EMBEDDING_MODEL) on :$EMBEDDING_PORT ==="
if docker ps -q -f name="$VLLM_EMBEDDING_CONTAINER" | grep -q .; then
  echo "  Already running."
else
  docker rm -f "$VLLM_EMBEDDING_CONTAINER" 2>/dev/null || true
  docker run -d \
    --name "$VLLM_EMBEDDING_CONTAINER" \
    --restart unless-stopped \
    --network=host \
    --gpus all \
    -e CUDA_VISIBLE_DEVICES="$EMBEDDING_GPUS" \
    "$VLLM_IMAGE" \
    "$EMBEDDING_MODEL" \
    --port $EMBEDDING_PORT \
    --tensor-parallel-size 1 \
    --max-model-len $EMBEDDING_MAX_MODEL_LEN \
    --dtype bfloat16 \
    --gpu-memory-utilization $EMBEDDING_GPU_MEM_UTIL \
    --trust-remote-code
  echo "  Started. Log: docker logs -f $VLLM_EMBEDDING_CONTAINER"
fi

# ============================================================
# 6. vLLM: intermediate LLM (4B)
# ============================================================
echo ""
echo "=== vLLM: intermediate ($INTERMEDIATE_MODEL) on :$INTERMEDIATE_PORT ==="
if docker ps -q -f name="$VLLM_INTERMEDIATE_CONTAINER" | grep -q .; then
  echo "  Already running."
else
  docker rm -f "$VLLM_INTERMEDIATE_CONTAINER" 2>/dev/null || true
  docker run -d \
    --name "$VLLM_INTERMEDIATE_CONTAINER" \
    --restart unless-stopped \
    --network=host \
    --gpus all \
    -e CUDA_VISIBLE_DEVICES="$INTERMEDIATE_GPUS" \
    "$VLLM_IMAGE" \
    "$INTERMEDIATE_MODEL" \
    --port $INTERMEDIATE_PORT \
    --tensor-parallel-size $INTERMEDIATE_TP \
    --max-model-len $INTERMEDIATE_MAX_MODEL_LEN \
    --dtype bfloat16 \
    --gpu-memory-utilization $INTERMEDIATE_GPU_MEM_UTIL \
    --enable-prefix-caching \
    --enable-chunked-prefill \
    --trust-remote-code
  echo "  Started. Log: docker logs -f $VLLM_INTERMEDIATE_CONTAINER"
fi

# ============================================================
# 7. vLLM: primary LLM (35B)
# ============================================================
echo ""
echo "=== vLLM: primary ($LLM_MODEL) on :$LLM_PORT ==="
if docker ps -q -f name="$VLLM_PRIMARY_CONTAINER" | grep -q .; then
  echo "  Already running."
else
  docker rm -f "$VLLM_PRIMARY_CONTAINER" 2>/dev/null || true
  docker run -d \
    --name "$VLLM_PRIMARY_CONTAINER" \
    --restart unless-stopped \
    --network=host \
    --gpus all \
    -e CUDA_VISIBLE_DEVICES="$LLM_GPUS" \
    "$VLLM_IMAGE" \
    "$LLM_MODEL" \
    --port $LLM_PORT \
    --tensor-parallel-size $LLM_TP \
    --max-model-len $LLM_MAX_MODEL_LEN \
    --dtype bfloat16 \
    --gpu-memory-utilization $LLM_GPU_MEM_UTIL \
    --enable-prefix-caching \
    --enable-chunked-prefill \
    --trust-remote-code
  echo "  Started. Log: docker logs -f $VLLM_PRIMARY_CONTAINER"
fi

# ============================================================
# 8. Wait for vLLM (model loading takes a few minutes)
# ============================================================
echo ""
echo "=== Waiting for vLLM servers (model loading takes a few minutes) ==="
wait_for_http "http://localhost:$EMBEDDING_PORT/health" "embedding vLLM" 300
wait_for_http "http://localhost:$INTERMEDIATE_PORT/health" "intermediate vLLM" 300
wait_for_http "http://localhost:$LLM_PORT/health" "primary vLLM" 300

# ============================================================
# 9. Optional ingestion
# ============================================================
if [ "$INGEST" = true ]; then
  echo ""
  echo "=== Ingestion: run manually from inside your app container ==="
  echo "  DGX=true PYTHONPATH=src python src/fse_ingestion/fse_ingestion.py"
fi

echo ""
echo "=== All services ready ==="
echo "  Qdrant:            http://localhost:$QDRANT_PORT"
echo "  PostgreSQL:        localhost:$POSTGRES_PORT"
echo "  vLLM primary:      http://localhost:$LLM_PORT"
echo "  vLLM intermediate: http://localhost:$INTERMEDIATE_PORT"
echo "  vLLM embedding:    http://localhost:$EMBEDDING_PORT"
echo ""
echo "Run eval:"
echo "  DGX=true PYTHONPATH=src pytest tests/test_eval_corpus.py -m eval -v"
echo ""
echo "vLLM logs:"
echo "  docker logs -f $VLLM_PRIMARY_CONTAINER"
echo "  docker logs -f $VLLM_INTERMEDIATE_CONTAINER"
echo "  docker logs -f $VLLM_EMBEDDING_CONTAINER"

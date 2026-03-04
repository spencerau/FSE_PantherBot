#!/bin/bash

# Simple cluster sync script that just syncs files, then provides instructions for manual container work

CLUSTER_HOST="mlat_desktop"
CLUSTER_USER="spencer"
REMOTE_PROJECT_DIR="/home/spencer/Documents/FSE_PantherBot"

echo "Syncing files to cluster..."

echo "Creating tar archive..."
tar -czf /tmp/pantherbot-sync.tar.gz \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='qdrant_data' \
    --exclude='postgres_data' \
    --exclude='.DS_Store' \
    . 2>&1 | grep -v -E "(Ignoring unknown extended header keyword|SCHILY\.fflags|LIBARCHIVE\.xattr)" || true

echo "Transferring files to cluster..."
scp /tmp/pantherbot-sync.tar.gz ${CLUSTER_USER}@${CLUSTER_HOST}:/tmp/

echo "Syncing code to cluster (preserving data directories)..."
ssh ${CLUSTER_USER}@${CLUSTER_HOST} "
    cd ${REMOTE_PROJECT_DIR%/*}
    
    # Create backup directory for code sync
    mkdir -p /tmp/code_sync
    cd /tmp/code_sync
    tar -xzf /tmp/pantherbot-sync.tar.gz 2>&1 | grep -v -E \"(Ignoring unknown extended header keyword|SCHILY\.fflags|LIBARCHIVE\.xattr)\" || true
    rm /tmp/pantherbot-sync.tar.gz
    
    # Sync only code files, preserving data directories
    rsync -av --exclude='qdrant_data' --exclude='postgres_data' /tmp/code_sync/ ${REMOTE_PROJECT_DIR}/
    
    # Cleanup temp directory
    rm -rf /tmp/code_sync
"

rm -f /tmp/pantherbot-sync.tar.gz

echo "Code synced to cluster! (Data directories preserved)"
echo ""
echo "Next steps (run on cluster):"
echo "1. ssh ${CLUSTER_HOST}"
echo "2. screen -S pantherbot"
echo "3. cd ${REMOTE_PROJECT_DIR##*/}"
echo "4. ./scripts/run_cluster.sh -f         # Start services (data persists)"
echo "   OR: ./scripts/run_cluster.sh -b -f  # Rebuild + start (data persists)"  
echo "   OR: ./scripts/run_cluster.sh -b -c -f  # Rebuild + clean data + fresh ingest"
echo ""
echo "Note: This will start TWO Ollama containers:"
echo "  - spencerau-ollama (main LLM on port 11434)"
echo "  - spencerau-intermediate-llm (routing/compression on port 11435)"
echo ""
echo "Monitor logs:"
echo "   docker logs -f spencerau-streamlit"
echo "   docker logs -f spencerau-ollama"
echo "   docker logs -f spencerau-intermediate-llm"
echo ""
echo "SSH tunnel: "
echo "ssh -L 8501:localhost:8501 -L 6333:localhost:6333 -L 11434:localhost:11434 -L 11435:localhost:11435 ${CLUSTER_USER}@${CLUSTER_HOST}"
echo "Visit: http://localhost:8501"

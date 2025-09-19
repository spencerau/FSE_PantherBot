#!/bin/bash

# Simple cluster sync script that just syncs files, then provides instructions for manual container work

CLUSTER_HOST="dgx0.chapman.edu"
CLUSTER_USER="spau"
REMOTE_PROJECT_DIR="/home/spau/FSE_PantherBot"

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
scp /tmp/pantherbot-sync.tar.gz spau@dgx0.chapman.edu:/tmp/

echo "Syncing code to cluster (preserving data directories)..."
ssh spau@dgx0.chapman.edu "
    cd /nfshome/spau
    
    # Create backup directory for code sync
    mkdir -p /tmp/code_sync
    cd /tmp/code_sync
    tar -xzf /tmp/pantherbot-sync.tar.gz 2>&1 | grep -v -E \"(Ignoring unknown extended header keyword|SCHILY\.fflags|LIBARCHIVE\.xattr)\" || true
    rm /tmp/pantherbot-sync.tar.gz
    
    # Sync only code files, preserving data directories
    rsync -av --exclude='qdrant_data' --exclude='postgres_data' /tmp/code_sync/ /nfshome/spau/FSE_PantherBot/
    
    # Cleanup temp directory
    rm -rf /tmp/code_sync
"

rm -f /tmp/pantherbot-sync.tar.gz

echo "Code synced to cluster! (Data directories preserved)"
echo ""
echo "Next steps (run on cluster):"
echo "1. ssh dgx0.chapman.edu"
echo "2. screen -S pantherbot"
echo "3. cd FSE_PantherBot"
echo "4. ./scripts/run_cluster.sh -f         # Start services (data persists)"
echo "   OR: ./scripts/run_cluster.sh -b -f  # Rebuild + start (data persists)"  
echo "   OR: ./scripts/run_cluster.sh -b -c -f  # Rebuild + clean data + fresh ingest"
echo ""
echo "Monitor logs:"
echo "   docker logs -f spencerau-streamlit"
echo ""
echo "SSH tunnel: "
echo "ssh -L 8501:localhost:8501 -L 6333:localhost:6333 spau@dgx0.chapman.edu"
echo "Visit: http://localhost:8501"

#!/bin/bash

# Ingest data via cluster (more stable for bulk embedding)
# This script syncs code to cluster, runs ingestion there, and copies qdrant_data back

set -e

CLUSTER_USER="spencerau"
CLUSTER_HOST="mlat.chapman.edu"
CLUSTER_PATH="~/FSE_PantherBot"

echo "=== Ingesting via Cluster ==="
echo ""

# Step 1: Sync code to cluster
echo "Step 1: Syncing code to cluster..."
./scripts/sync_to_cluster.sh
echo ""

# Step 2: Run ingestion on cluster
echo "Step 2: Running ingestion on cluster..."
ssh ${CLUSTER_USER}@${CLUSTER_HOST} "cd ${CLUSTER_PATH} && ./scripts/run_cluster.sh -c"
echo ""

# Step 3: Copy qdrant_data back to local
echo "Step 3: Copying qdrant_data from cluster to local..."
echo "Removing old local qdrant_data..."
rm -rf ./qdrant_data

echo "Downloading qdrant_data from cluster..."
scp -r ${CLUSTER_USER}@${CLUSTER_HOST}:${CLUSTER_PATH}/qdrant_data ./

echo ""
echo "=== Ingestion Complete ==="
echo "Qdrant data successfully ingested via cluster and copied to local"
echo ""
echo "Next steps:"
echo "  - Start local services: ./scripts/run_local.sh"
echo "  - Or test directly: PYTHONPATH=src streamlit run streamlit_app.py"

#!/bin/bash
# Sync code to DGX cluster (excludes data volumes, venv, caches).
# Set DGX_HOST to your SSH alias/hostname, or configure it below.
#
# Usage: ./scripts/sync_to_dgx.sh [--dry-run]

set -e

# Override via environment: DGX_HOST=myalias ./scripts/sync_to_dgx.sh
DGX_HOST="${DGX_HOST:-dgx_cluster}"
DGX_PATH="${DGX_PATH:-~/FSE_PantherBot}"

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run|-n) DRY_RUN=true; shift ;;
    --help|-h)
      echo "Usage: $0 [--dry-run]"
      echo "  Set DGX_HOST env var or edit this script to set your SSH alias."
      exit 0 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

RSYNC_ARGS="-avz --progress"
if [ "$DRY_RUN" = true ]; then
  RSYNC_ARGS="$RSYNC_ARGS --dry-run"
  echo "=== DRY RUN — no files will be transferred ==="
fi

echo "=== Syncing to $DGX_HOST:$DGX_PATH ==="

# Ensure remote directory exists
ssh "$DGX_HOST" "mkdir -p $DGX_PATH"

rsync $RSYNC_ARGS \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='*.pyc' \
  --exclude='.DS_Store' \
  --exclude='qdrant_data' \
  --exclude='postgres_data' \
  --exclude='.venv' \
  --exclude='*.log' \
  --exclude='.reports' \
  --exclude='*.egg-info' \
  --exclude='.pytest_cache' \
  "$REPO_DIR/" \
  "$DGX_HOST:$DGX_PATH/"

echo ""
echo "=== Sync complete ==="
echo ""
echo "Next steps on DGX:"
echo "  ssh $DGX_HOST"
echo "  cd FSE_PantherBot"
echo "  pip install -e . -q                        # if dependencies changed"
echo "  ./scripts/dgx_up.sh                        # start services"
echo "  ./scripts/dgx_up.sh --clean --ingest       # start fresh + re-ingest"
echo ""
echo "Run eval:"
echo "  DGX=true PYTHONPATH=src .venv/bin/pytest tests/test_eval_corpus.py -m eval -v"

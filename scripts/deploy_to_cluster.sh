#!/bin/bash

# Cluster deployment script for SSH + container workflow
# This script helps deploy and manage PantherBot on a headless compute cluster

set -e  # Exit on any error

# Configuration (update these values)
CLUSTER_HOST="dgx0.chapman.edu"
CLUSTER_USER="spau"
SSH_KEY_PATH="~/.ssh/id_rsa"  # Path to your SSH key (not needed since keys are already setup)
CONTAINER_NAME="ollama-spencerau"  # Your existing container name
REMOTE_PROJECT_DIR="/home/$CLUSTER_USER/FSE_PantherBot"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check SSH connectivity
check_ssh() {
    log_info "Checking SSH connectivity to $CLUSTER_HOST..."
    if ssh -o ConnectTimeout=10 "$CLUSTER_USER@$CLUSTER_HOST" "echo 'SSH connection successful'"; then
        log_info "SSH connection established"
        return 0
    else
        log_error "SSH connection failed"
        return 1
    fi
}

# Function to sync project files to cluster
sync_to_cluster() {
    log_info "Syncing project files to cluster..."
    
    # Create remote directory if it doesn't exist
    ssh "$CLUSTER_USER@$CLUSTER_HOST" "mkdir -p $REMOTE_PROJECT_DIR"
    
    # Sync files (excluding .git, __pycache__, etc.)
    rsync -avz --progress \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.DS_Store' \
        --exclude='qdrant_data' \
        --exclude='postgres_data' \
        . "$CLUSTER_USER@$CLUSTER_HOST:$REMOTE_PROJECT_DIR/"
    
    log_info "Project files synced successfully"
}

# Function to setup container on cluster
setup_container() {
    log_info "Setting up existing container on cluster..."
    
    ssh "$CLUSTER_USER@$CLUSTER_HOST" << EOF
        cd $REMOTE_PROJECT_DIR
        
        # Check if your existing container is running
        if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            echo "Container $CONTAINER_NAME is already running"
        elif docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
            echo "Starting existing container $CONTAINER_NAME..."
            docker start $CONTAINER_NAME
        else
            echo "Error: Container $CONTAINER_NAME not found"
            echo "Available containers:"
            docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
            exit 1
        fi
        
        echo "Container $CONTAINER_NAME is ready"
EOF
}

# Function to pull models in container
pull_models() {
    log_info "Pulling models in cluster container..."
    
    ssh "$CLUSTER_USER@$CLUSTER_HOST" << EOF
        # Check if Ollama is running in container
        if ! docker exec $CONTAINER_NAME pgrep ollama > /dev/null; then
            echo "Starting Ollama service in container..."
            docker exec -d $CONTAINER_NAME ollama serve
            sleep 10
        fi
        
        # Pull the large models
        echo "Pulling deepseek-r1:70b (this will take a while)..."
        docker exec $CONTAINER_NAME ollama pull deepseek-r1:70b
        
        echo "Pulling bge-m3:567m..."
        docker exec $CONTAINER_NAME ollama pull bge-m3:567m
        
        # List available models
        echo "Available models:"
        docker exec $CONTAINER_NAME ollama list
EOF
}

# Function to start the RAG system
start_rag_system() {
    log_info "Starting RAG system in cluster container..."
    
    ssh "$CLUSTER_USER@$CLUSTER_HOST" << EOF
        cd $REMOTE_PROJECT_DIR
        
        # Install Python dependencies in container
        docker exec $CONTAINER_NAME bash -c "
            apt-get update && apt-get install -y python3 python3-pip
            pip3 install -r /app/requirements.txt
        "
        
        # Start the system
        docker exec -d $CONTAINER_NAME bash -c "
            cd /app && PYTHONPATH=/app/src python3 -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
        "
        
        echo "RAG system started. Access it via SSH tunnel:"
        echo "ssh -L 8501:localhost:8501 -L 11434:localhost:11434 $CLUSTER_USER@$CLUSTER_HOST"
EOF
}

# Function to create SSH tunnel
create_tunnel() {
    log_info "Creating SSH tunnel for local access..."
    echo "Run this command to create SSH tunnel:"
    echo "ssh -L 8501:localhost:8501 -L 11434:localhost:11434 -L 6333:localhost:6333 $CLUSTER_USER@$CLUSTER_HOST"
    echo ""
    echo "Then access:"
    echo "  - Streamlit UI: http://localhost:8501"
    echo "  - Ollama API: http://localhost:11434"
    echo "  - Qdrant: http://localhost:6333"
}

# Function to show container status
show_status() {
    log_info "Checking cluster container status..."
    
    ssh "$CLUSTER_USER@$CLUSTER_HOST" << EOF
        echo "Container status:"
        docker ps --filter name=$CONTAINER_NAME
        echo ""
        echo "Container logs (last 20 lines):"
        docker logs --tail 20 $CONTAINER_NAME
EOF
}

# Main script logic
case "${1:-help}" in
    "setup")
        check_ssh && sync_to_cluster && setup_container && pull_models
        ;;
    "sync")
        check_ssh && sync_to_cluster
        ;;
    "models")
        check_ssh && pull_models
        ;;
    "start")
        check_ssh && start_rag_system
        ;;
    "tunnel")
        create_tunnel
        ;;
    "status")
        check_ssh && show_status
        ;;
    "help"|*)
        echo "Usage: $0 {setup|sync|models|start|tunnel|status}"
        echo ""
        echo "Commands:"
        echo "  setup   - Complete setup: sync files, create container, pull models"
        echo "  sync    - Sync project files to cluster"
        echo "  models  - Pull required models in cluster container"
        echo "  start   - Start the RAG system in cluster"
        echo "  tunnel  - Show SSH tunnel command for local access"
        echo "  status  - Show cluster container status"
        echo ""
        echo "Before running, update the configuration variables at the top of this script"
        ;;
esac

#!/bin/bash

# Quick cluster operations script for PantherBot
#        echo "📥 Pulling xitao/bge-reranker-v2-m3..."
        docker exec ollama-spencerau ollama pull xitao/bge-reranker-v2-m3or use with existing container: ollama-spencerau on dgx0.chapman.edu

CLUSTER_HOST="dgx0.chapman.edu"
CLUSTER_USER="spau"
CONTAINER_NAME="ollama-spencerau"
REMOTE_PROJECT_DIR="/home/spau/FSE_PantherBot"

# Quick sync and run
quick_deploy() {
    echo "🚀 Quick deployment to cluster..."
    
    # Sync files
    echo "📁 Syncing files..."
    rsync -avz --progress \
        --exclude='.git' \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.DS_Store' \
        --exclude='qdrant_data' \
        --exclude='postgres_data' \
        . "$CLUSTER_USER@$CLUSTER_HOST:$REMOTE_PROJECT_DIR/"
    
    # Copy files into container and start
    ssh "$CLUSTER_USER@$CLUSTER_HOST" << 'EOF'
        echo "📦 Copying files to container..."
        docker cp /home/spau/FSE_PantherBot/. ollama-spencerau:/app/
        
        echo "🔄 Installing/updating dependencies..."
        docker exec ollama-spencerau bash -c "
            cd /app
            pip3 install -r requirements.txt --quiet
        "
        
        echo "🤖 Starting Ollama service..."
        docker exec -d ollama-spencerau ollama serve
        
        echo "🧠 Starting RAG system..."
        docker exec -d ollama-spencerau bash -c "
            cd /app && PYTHONPATH=/app/src python3 -m streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8501
        "
        
        echo "✅ System started! Create SSH tunnel with:"
        echo "ssh -L 8501:localhost:8501 -L 11434:localhost:11434 spau@dgx0.chapman.edu"
EOF
}

# Pull models
pull_models() {
    echo "📥 Pulling models on cluster..."
    ssh "$CLUSTER_USER@$CLUSTER_HOST" << 'EOF'
        echo "🔄 Ensuring Ollama is running..."
        docker exec -d ollama-spencerau ollama serve
        sleep 5
        
        echo "📥 Pulling deepseek-r1:70b..."
        docker exec ollama-spencerau ollama pull deepseek-r1:70b
        
        echo "📥 Pulling bge-m3:567m..."
        docker exec ollama-spencerau ollama pull bge-m3:567m
        
        echo "� Pulling bge-reranker-v2-m3..."
        docker exec ollama-spencerau ollama pull bge-reranker-v2-m3
        
        echo "�📋 Available models:"
        docker exec ollama-spencerau ollama list
EOF
}

# Check status
check_status() {
    echo "📊 Checking cluster status..."
    ssh "$CLUSTER_USER@$CLUSTER_HOST" << 'EOF'
        echo "🐳 All containers:"
        docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
        
        echo -e "\n🔍 Looking for ollama containers:"
        docker ps -a --filter ancestor=ollama/ollama --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
        
        echo -e "\n🧠 Checking if any ollama service is running:"
        docker ps --filter ancestor=ollama/ollama --format "{{.Names}}" | head -1 | xargs -r docker exec {} ollama list 2>/dev/null || echo "No running ollama containers found"
EOF
}

# Show tunnel command
show_tunnel() {
    echo "🌐 SSH Tunnel command:"
    echo "ssh -L 8501:localhost:8501 -L 11434:localhost:11434 -L 6333:localhost:6333 spau@dgx0.chapman.edu"
    echo ""
    echo "Then access:"
    echo "  🖥️  Streamlit UI: http://localhost:8501"
    echo "  🤖 Ollama API: http://localhost:11434"
    echo "  🔍 Qdrant: http://localhost:6333"
}

# Test connection
test_models() {
    echo "🧪 Testing models on cluster..."
    ssh "$CLUSTER_USER@$CLUSTER_HOST" << 'EOF'
        echo "Testing deepseek-r1:70b..."
        docker exec ollama-spencerau ollama run deepseek-r1:70b "Hello, this is a test. Please respond briefly." || echo "❌ deepseek-r1:70b not available"
        
        echo -e "\nTesting embedding model..."
        docker exec ollama-spencerau curl -s http://localhost:11434/api/embeddings -d '{"model":"bge-m3:567m","prompt":"test"}' | head -c 100 || echo "❌ bge-m3:567m not available"
        
        echo -e "\nTesting reranker model..."
        docker exec ollama-spencerau curl -s http://localhost:11434/api/embeddings -d '{"model":"xitao/bge-reranker-v2-m3","prompt":"Query: test\nDocument: sample text"}' | head -c 100 || echo "❌ xitao/bge-reranker-v2-m3 not available"
EOF
}

# Detect actual container name
detect_container() {
    echo "🔍 Detecting ollama container..."
    ssh "$CLUSTER_USER@$CLUSTER_HOST" << 'EOF'
        echo "Looking for ollama containers..."
        CONTAINER_NAME=$(docker ps -a --filter ancestor=ollama/ollama --format "{{.Names}}" | head -1)
        
        if [ -z "$CONTAINER_NAME" ]; then
            echo "❌ No ollama containers found!"
            echo "Available containers:"
            docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
        else
            echo "✅ Found ollama container: $CONTAINER_NAME"
            echo "Status:"
            docker ps --filter name=$CONTAINER_NAME --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
            
            # Check if it's running
            if docker ps --filter name=$CONTAINER_NAME --quiet | grep -q .; then
                echo "✅ Container is running"
            else
                echo "⚠️  Container exists but is not running. Starting..."
                docker start $CONTAINER_NAME
            fi
        fi
EOF
}

case "${1:-help}" in
    "deploy"|"quick")
        quick_deploy
        ;;
    "models")
        pull_models
        ;;
    "status")
        check_status
        ;;
    "detect")
        detect_container
        ;;
    "tunnel")
        show_tunnel
        ;;
    "test")
        test_models
        ;;
    "help"|*)
        echo "🚀 PantherBot Cluster Quick Commands"
        echo ""
        echo "Usage: $0 {deploy|models|status|detect|tunnel|test}"
        echo ""
        echo "Commands:"
        echo "  deploy  - Sync files and start system on cluster"
        echo "  models  - Pull required models (deepseek-r1:70b, bge-m3:567m)"
        echo "  status  - Check container and system status"
        echo "  detect  - Find and start ollama container"
        echo "  tunnel  - Show SSH tunnel command"
        echo "  test    - Test model availability and functionality"
        ;;
esac

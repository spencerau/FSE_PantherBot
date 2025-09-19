#!/bin/bash

echo "Starting memory compression service..."

cd /app

# Function to wait for PostgreSQL to be ready
wait_for_postgres() {
    echo "Waiting for PostgreSQL to be ready..."
    
    # Source environment variables only if they're not already set
    if [ -f "src/memory/.env" ]; then
        # Only set variables that aren't already defined
        while IFS='=' read -r key value; do
            # Skip comments and empty lines
            [[ $key =~ ^#.*$ ]] && continue
            [[ -z "$key" ]] && continue
            
            # Only export if not already set
            if [ -z "${!key}" ]; then
                export "$key=$value"
            fi
        done < <(grep -v '^#' src/memory/.env | grep -v '^$')
    fi
    
    POSTGRES_HOST=${POSTGRES_HOST:-postgres}
    POSTGRES_PORT=${POSTGRES_PORT:-5432}
    
    for i in {1..60}; do
        # Use timeout and /dev/tcp if available, otherwise use python as fallback
        if timeout 3 bash -c "</dev/tcp/$POSTGRES_HOST/$POSTGRES_PORT" 2>/dev/null; then
            echo "PostgreSQL port is open, waiting 5 more seconds for full startup..."
            sleep 5
            echo "PostgreSQL is ready!"
            return 0
        elif python -c "import socket; s=socket.socket(); s.settimeout(3); s.connect(('$POSTGRES_HOST', $POSTGRES_PORT)); s.close()" 2>/dev/null; then
            echo "PostgreSQL port is open (via python), waiting 5 more seconds for full startup..."
            sleep 5
            echo "PostgreSQL is ready!"
            return 0
        fi
        
        echo "Attempt $i/60: PostgreSQL not ready, waiting 5 seconds..."
        sleep 5
    done
    
    echo "ERROR: PostgreSQL did not become ready within 5 minutes"
    return 1
}

# Wait for PostgreSQL before starting the compression loop
if ! wait_for_postgres; then
    echo "Failed to connect to PostgreSQL. Exiting."
    exit 1
fi

while true; do
    echo "$(date): Running memory compression..."
    python src/memory/compress_memory.py
    
    echo "$(date): Memory compression completed. Sleeping for 5 minutes..."
    sleep 300
done

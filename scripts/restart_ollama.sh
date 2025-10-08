#!/bin/bash

# Restart Ollama container to prevent GPU context issues
# This script should be run daily via crontab

set -e

CONTAINER_NAME="spencerau-ollama"
LOG_FILE="/tmp/ollama_restart.log"

echo "$(date): Starting Ollama container restart" >> "$LOG_FILE"

# Check if container exists and is running
if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
    echo "$(date): Stopping container $CONTAINER_NAME" >> "$LOG_FILE"
    docker stop "$CONTAINER_NAME"
    
    echo "$(date): Starting container $CONTAINER_NAME" >> "$LOG_FILE"
    docker start "$CONTAINER_NAME"
    
    # Wait a moment and verify it's running
    sleep 10
    if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
        echo "$(date): Container restart successful" >> "$LOG_FILE"
    else
        echo "$(date): ERROR: Container failed to start after restart" >> "$LOG_FILE"
        exit 1
    fi
else
    echo "$(date): Container $CONTAINER_NAME not found or not running" >> "$LOG_FILE"
    exit 1
fi

echo "$(date): Restart completed successfully" >> "$LOG_FILE"
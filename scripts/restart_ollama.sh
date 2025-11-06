#!/bin/bash

# Restart Ollama containers to prevent GPU context issues
# This script should be run daily via crontab

set -e

MAIN_CONTAINER="spencerau-ollama"
INTERMEDIATE_CONTAINER="spencerau-intermediate-llm"
LOG_FILE="/tmp/ollama_restart.log"

echo "$(date): Starting Ollama containers restart" >> "$LOG_FILE"

# Restart main Ollama container
if docker ps -q -f name="$MAIN_CONTAINER" | grep -q .; then
    echo "$(date): Stopping container $MAIN_CONTAINER" >> "$LOG_FILE"
    docker stop "$MAIN_CONTAINER"
    
    echo "$(date): Starting container $MAIN_CONTAINER" >> "$LOG_FILE"
    docker start "$MAIN_CONTAINER"
    
    # Wait a moment and verify it's running
    sleep 10
    if docker ps -q -f name="$MAIN_CONTAINER" | grep -q .; then
        echo "$(date): Main container restart successful" >> "$LOG_FILE"
    else
        echo "$(date): ERROR: Main container failed to start after restart" >> "$LOG_FILE"
        exit 1
    fi
else
    echo "$(date): Container $MAIN_CONTAINER not found or not running" >> "$LOG_FILE"
fi

# Restart intermediate LLM container
if docker ps -q -f name="$INTERMEDIATE_CONTAINER" | grep -q .; then
    echo "$(date): Stopping container $INTERMEDIATE_CONTAINER" >> "$LOG_FILE"
    docker stop "$INTERMEDIATE_CONTAINER"
    
    echo "$(date): Starting container $INTERMEDIATE_CONTAINER" >> "$LOG_FILE"
    docker start "$INTERMEDIATE_CONTAINER"
    
    # Wait a moment and verify it's running
    sleep 10
    if docker ps -q -f name="$INTERMEDIATE_CONTAINER" | grep -q .; then
        echo "$(date): Intermediate LLM container restart successful" >> "$LOG_FILE"
    else
        echo "$(date): ERROR: Intermediate LLM container failed to start after restart" >> "$LOG_FILE"
        exit 1
    fi
else
    echo "$(date): Container $INTERMEDIATE_CONTAINER not found or not running" >> "$LOG_FILE"
fi

echo "$(date): All Ollama containers restart completed successfully" >> "$LOG_FILE"
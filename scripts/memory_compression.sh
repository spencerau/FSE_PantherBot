#!/bin/bash

echo "Starting memory compression service..."

cd /app

while true; do
    echo "$(date): Running memory compression..."
    python src/memory/compress_memory.py
    
    echo "$(date): Memory compression completed. Sleeping for 12 hours..."
    sleep 43200
done

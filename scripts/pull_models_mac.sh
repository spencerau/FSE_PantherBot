#!/bin/bash

echo "Starting containers if not running..."
docker compose up -d

echo "Pulling models to Ollama container..."
# Primary models for cluster deployment
docker compose exec ollama ollama pull deepseek-r1:70b
docker compose exec ollama ollama pull bge-m3:567m

# Fallback models for local development  
docker compose exec ollama ollama pull gemma3:4b
docker compose exec ollama ollama pull nomic-embed-text

echo "Listing available models:"
docker compose exec ollama ollama list

echo "Models are ready for use"
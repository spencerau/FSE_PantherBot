#!/bin/bash

echo "Starting containers if not running..."
docker compose up -d

echo "Pulling models to Ollama container..."
docker compose exec ollama ollama pull deepseek-r1:1.5b
docker compose exec ollama ollama pull nomic-embed-text

echo "Listing available models:"
docker compose exec ollama ollama list

echo "Models are ready for use"
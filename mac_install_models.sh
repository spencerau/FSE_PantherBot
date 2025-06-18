#!/bin/bash

# Pull the LLM model
docker exec -it rowboat-ollama-1 ollama pull deepseek-r1:1.5b

# Pull the embedding model
docker exec -it rowboat-ollama-1 ollama pull nomic-embed-text
#!/bin/bash
# Ensure Docker Desktop is launched
open -a Docker
echo "Waiting for Docker to start..."
timeout=60
while ! docker ps &>/dev/null; do
  timeout=$((timeout - 1))
  if [[ $timeout -le 0 ]]; then
    echo "🛑 Docker did not start in time!"
    exit 1
  fi
  sleep 1
done

# Launch Ollama in the background
echo "Starting Ollama..."
ollama run deepseek-r1:1.5b &

# Finally invoke Rowboat
cd rowboat
./start.sh
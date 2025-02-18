#!/bin/bash

# prob need to change this so it can pull a install dir from the cli args
export OLLAMA_MODELS="$(pwd)/ollama"
mkdir -p "$OLLAMA_MODELS"

export OLLAMA_MODELS="$OLLAMA_MODELS"

# Models to install
models=("deepseek-r1:7b")

for model in "${models[@]}"; do
    echo "Checking if model '$model' is available..."
    if ollama list | grep -q "$model"; then
        echo "Model '$model' is already installed."
    else
        echo "Downloading model '$model'..."
        ollama pull "$model"
        echo "Model '$model' downloaded."
    fi
done

# this doesn't install locally within the pwd
#echo "Setup complete! Ollama models are stored in $OLLAMA_MODELS and ready to use."
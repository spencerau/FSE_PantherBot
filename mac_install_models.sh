#!/bin/bash

# Ensure Ollama is installed
# if ! command -v ollama &> /dev/null; then
#     echo "Ollama is not installed. Installing Ollama..."
#     brew install ollama/tap/ollama
# else
#     echo "Ollama is already installed."
# fi

export OLLAMA_MODELS="$(pwd)/ollama"
mkdir -p "$OLLAMA_MODELS"
launchctl setenv OLLAMA_MODELS "$OLLAMA_MODELS"

# Models to install
models=("llama3.2" "mistral")

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

echo "Setup complete! Ollama models are stored in $OLLAMA_MODELS and ready to use."
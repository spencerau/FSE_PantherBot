#!/bin/bash

# Load environment variables from .env file
export $(grep -v '^#' .env | xargs)

# Log in with Hugging Face CLI
huggingface-cli login --token $HF_TOKEN

# Download a model or dataset
#huggingface-cli download meta-llama/LLaMA-13B
huggingface-cli download meta-llama/Llama-3.2-3B-Instruct
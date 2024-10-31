#!/bin/bash

if ! command -v conda &> /dev/null
then
    echo "Conda not found. Please install Conda first."
    exit
fi

ENV_NAME="pantherbot"

echo "Creating Conda environment: $ENV_NAME"
conda create -y -n $ENV_NAME python=3.10

echo "Activating Conda environment: $ENV_NAME"
source $(conda info --base)/etc/profile.d/conda.sh
conda activate $ENV_NAME

if [[ -f "requirements.txt" ]]; then
    echo "Installing dependencies from requirements.txt"
    pip install -r requirements.txt
else
    echo "requirements.txt not found. Please add it to the project directory."
    exit
fi

# Conditionally install FAISS
if [[ "$OSTYPE" == "darwin"* ]] && [[ "$(uname -m)" == "arm64" ]]; then
    echo "macOS ARM detected. Installing faiss-cpu."
    conda install -c conda-forge faiss-cpu
else
    echo "Linux or compatible GPU system detected. Installing faiss-gpu."
    conda install -c conda-forge faiss-gpu
fi

echo "Environment $ENV_NAME setup complete. To activate, run 'conda activate $ENV_NAME'."
#!/bin/bash

if ! command -v conda &> /dev/null
then
    echo "Conda not found. Please install Conda first."
    exit
fi

ENV_NAME="pantherbot"

export CONDA_BUILD_SYSROOT=$(xcrun --sdk macosx --show-sdk-path)

echo "Creating Conda environment: $ENV_NAME"
conda create -y -n $ENV_NAME python=3.10

echo "Activating Conda environment: $ENV_NAME"
source $(conda info --base)/etc/profile.d/conda.sh
conda activate $ENV_NAME

# Conditionally install FAISS
if [[ "$OSTYPE" == "darwin"* ]] && [[ "$(uname -m)" == "arm64" ]]; then
    # Set architecture flag to avoid compilation issues
    echo "Installing necessary compiler toolchains"
    conda install -y -c conda-forge clang_osx-64 clangxx_osx-64
    export ARCHFLAGS="-arch arm64"
    export CFLAGS="-isysroot $(xcrun --sdk macosx --show-sdk-path) -I$(xcrun --show-sdk-path)/usr/include"
    export CXXFLAGS="-isysroot $(xcrun --sdk macosx --show-sdk-path) -I$(xcrun --show-sdk-path)/usr/include"
    echo "macOS ARM detected. Installing faiss-cpu."
    conda install -c conda-forge faiss-cpu
else
    echo "Linux or compatible GPU system detected. Installing faiss-gpu."
    conda install -c conda-forge faiss-gpu
fi

echo "Using Nvidia NeMO Documentation for Apple Silicon"
# [optional] install mecab using Homebrew, to use sacrebleu for NLP collection
# you can install Homebrew here: https://brew.sh
brew install mecab

# [optional] install pynini using Conda, to use text normalization
conda install -c conda-forge pynini

# install Cython manually
# conda install -y cython packaging
pip install cython packaging

# clone the repo and install in development mode
git clone https://github.com/NVIDIA/NeMo
cd NeMo
pip install --use-pep517 'nemo_toolkit[all]'
#conda install -y nemo_toolkit[all]
cd ..

# Note that only the ASR toolkit is guaranteed to work on MacBook - so for MacBook use pip install 'nemo_toolkit[asr]'

# echo "Installing Cython and GCC with Conda to avoid dependency issues"
# # conda install -y cython
# # conda install -y -c conda-forge gcc
# pip install cython packaging

if [[ -f "requirements.txt" ]]; then
    echo "Installing dependencies from requirements.txt"
    pip install -r requirements.txt
else
    echo "requirements.txt not found. Please add it to the project directory."
    exit
fi


echo "Environment $ENV_NAME setup complete. To activate, run 'conda activate $ENV_NAME'."
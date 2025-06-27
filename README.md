# FSE_PantherBot
Creating an LLM to assist with Academic Advising within the Chapman Fowler School of Engineering

## Introduction
This project is a locally hosted AI-powered academic advising platform designed for undergraduate students. It leverages large language models (LLMs) and a Retrieval-Augmented Generation (RAG) pipeline to provide 24/7, context-aware academic support. By integrating document extraction (via Apache Tika), vector search/database (Qdrant), and modern LLMs through Ollama, the system can ingest and understand university catalogs, course data, and other resources, enabling students to ask questions and receive accurate, personalized guidance at any time—without sending their data to the cloud.

## Getting Started

## Streamlit
- Run `pull_models_mac.sh` once to pull the models into the Ollama Docker Container
- Run `docker compose up -d` to start the Docker containers
- Head to `http://localhost:8501/` to test out the Streamlit interface

## Configuration
- See [`configs/README.md`](configs/README.md) for configuration details and options.

## Testing
- Run `run_tests.sh -b` to run tests on various RAG componenets of the project
- If rebuilding the containers is not necessary, run `run_tests.sh` to run the tests without rebuilding the containers
- Only need to rebuild containers if making changes to Dockerfiles or requirements.txt files

<!-- ## Rowboat Stuff
`docker compose -f rowboat/docker-compose.yml -f rowboat_overrides/docker-compose.local.yml down`
`docker compose -f rowboat/docker-compose.yml -f rowboat_overrides/docker-compose.local.yml up -d`

- Head to localhost:3000 to test out the rowboat interface -->

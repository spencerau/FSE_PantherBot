# FSE_PantherBot
Creating an LLM to assist with Academic Advising within the Chapman Fowler School of Engineering

## Introduction
This project is a locally hosted AI-powered academic advising platform designed for undergraduate students. It leverages large language models (LLMs) and a Retrieval-Augmented Generation (RAG) pipeline to provide 24/7, context-aware academic support. By integrating document extraction (via Apache Tika), vector search/database (Qdrant), and modern LLMs through Ollama, the system can ingest and understand university catalogs, course data, and other resources, enabling students to ask questions and receive accurate, personalized guidance at any time—without sending their data to the cloud.

## Getting Started

## Streamlit
- Run `pull_models_mac.sh` once to pull the models into the Ollama Docker Container
- Run `docker compose up -d` to start the Docker containers
- Run with `PYTHONPATH=src streamlit run streamlit_app.py`
- Head to `http://localhost:8501/` to test out the Streamlit interface

## Configuration
- See [`configs/README.md`](configs/README.md) for configuration details and options.

## Usage
- `./run.sh [-b] [-t] [-c]`
	•	-b : Rebuild the Docker containers before running
	•	-t : Run all test cases in tests
	•	-c : Clean all Qdrant collections before ingestion

- Only need to rebuild containers if making changes to Dockerfiles or requirements.txt files

# MCP Server
To run the MCP server:
```bash
scripts/run_mcp.sh
```
Configure host, port, and transport in `configs/default.yaml`.

## Streamlit MCP Mode
In the Streamlit app, enable "Use MCP server" to route requests through MCP tools. The "Debug" expander shows retrieval lists, fused ranks, rerank scores, and citations.

## Slack Bot Integration
A Slack bot can call MCP tools via an MCP client. Use the stable tool/resource names and schemas as defined in the MCP server.

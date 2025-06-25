# FSE_PantherBot
Creating an LLM to assist with Academic Advising within the Chapman Fowler School of Engineering

## Getting Started

## Streamlit
Run `pull_models_mac.sh` once to pull the models into the Ollama Docker Container
Run `docker compose up -d` to start the Docker containers
Head to localhost:8501 to test out the Streamlit interface

## Testing
Run `run_tests.sh -b` to run tests on various RAG componenets of the project
If rebuilding the containers is not necessary, run `run_tests.sh` to run the tests without rebuilding the containers
Only need to rebuild containers if making changes to Dockerfiles or requirements.txt files


## Rowboat Stuff
<!-- Run ollama with `ollama run deepseek-r1:1b`  -->
docker compose -f rowboat/docker-compose.yml -f rowboat_overrides/docker-compose.local.yml down
docker compose -f rowboat/docker-compose.yml -f rowboat_overrides/docker-compose.local.yml up -d

Head to localhost:3000 to test out the rowboat interface

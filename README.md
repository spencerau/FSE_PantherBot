# FSE_PantherBot
Creating an LLM to assist with Academic Advising within the Chapman Fowler School of Engineering

## Getting Started
Run `chmod +x setup_conda.sh` to make the script executable.

Then run `./setup_conda.sh` to install the necessary dependencies and create the conda environment.

Finally, run `conda activate pantherbot` to activate the conda environment.

Install ollama from [here - ollama download link](https://ollama.com/download)

Install the models on ollama by running 'mac_install_models.sh`

## Setting Parameters via YAML config

The `config.yaml` file contains all the parameters that can be set for the LLM.
[Go to Yaml Config Documentation](configs/README.md)

## Running DeepSeek-R1 (Mac as of now)

Run `python src/main.py` to test the installation of ollama.

![Example Use](/assets/deepseek-example.png)

## TODO:

### General Stuff
- Use verbose mode to omit or include the `<think>` text of the output
- Grab CLI args and slap them into the YAML config if necessary
- Clear out various subdir and files that aren't being used
- Update documentation accordingly

### Vector DB and Retrieval/RAG Stuff
- Fix chunking, etc of csv
- Fix chunking, etc of the subdir as the retrieval doesnt seem to be working
- Perform some basic EDA on pdf and other data and then dyanmically create YAML config as well as store in separate? Vector DB for various sizes
- Could also store different course catalogs in different vectordbs based on when the student joined; so if they joined in 2023, they would pull responses from the 2023 db
- Need it to be on an actual server so that it can be accessed by multiple people/threads as well as be persistent 
- Put information that is told to the model through a vector db so it can be retrieved in subsequent conversations, etc

### Frontend Stuff
- Use Streamlit, etc to create a web interface for the LLM
- Integrate with Slack; test out with MLAT Slack server for an initial demo

### Testing Stuff
- Create a more robust testing suite and integrate into PR, etc (because i look like an asshole if i submit this as my thesis with commented print statements)
- Create testing with a list of questions so i can examine the expected answers

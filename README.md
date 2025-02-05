# FSE_PantherBot
Creating an LLM to assist with Academic Advising within the Chapman Fowler School of Engineering

## Getting Started
Run `chmod +x setup_conda.sh` to make the script executable.

Then run `./setup_conda.sh` to install the necessary dependencies and create the conda environment.

Finally, run `conda activate pantherbot` to activate the conda environment.

Install ollama from [here - ollama download link](https://ollama.com/download)

Install the models on ollama by running 'mac_install_models.sh`

## Running DeepSeek-R1 (Mac as of now)

Run `python tests/ollama_test.py` to test the installation of ollama.

![Example Use](/assets/deepseek-example.png)

## TODO:

- Use verbose mode to omit or include the `<think>` text of the output
- Grab CLI args and slap them into the YAML config if necessary
- Fix chunking, etc of csv
- Fix chunking, etc of the subdir as the retrieval doesnt seem to be working
- Clear out various subdir and files that aren't being used
- Use Streamlit, etc to create a web interface for the LLM
- Integrate with Slacks; test out with MLAT Slack server for an initial demo
- Update documentation accordingly
- Create a more robust testing suite and integrate into PR, etc (because i look like an asshole if i submit this as my thesis with commented print statements)
- Create testing with a list of questions so i can examine the expected answers

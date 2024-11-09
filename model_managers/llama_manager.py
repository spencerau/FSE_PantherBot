# models/llama_manager.py

import yaml
import ollama


class LLaMAModel:
    def __init__(self, config_path):
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)
        
        self.model_name = config['models']['llama']['model_name']
        self.max_length = config['models']['llama']['max_length']
        self.temperature = config['models']['llama']['temperature']
        self.top_p = config['models']['llama']['top_p']

    def stream_generate(self, input_text):
        # stream so that generates responses in chunks in real time
        stream = ollama.chat(
            model=self.model_name,
            messages=[{'role': 'user', 'content': input_text}],
            stream=True
        )
        
        for chunk in stream:
            yield chunk['message']['content']
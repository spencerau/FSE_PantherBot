# Loads LLaMA locally via Hugging Face or Meta’s preferred method

# models/llama_manager.py
import yaml
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


class LLaMAModel:
    def __init__(self, config_path="../configs/model_config.yaml"):
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)
        
        model_name = config['models']['llama']['model_name']
        tokenizer_name = config['models']['llama']['tokenizer_name']
        self.max_length = config['models']['llama']['max_length']
        self.temperature = config['models']['llama']['temperature']
        self.top_p = config['models']['llama']['top_p']
        
        # Load tokenizer and model
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.model.to(config['models']['llama']['device'])


    def generate(self, input_text):
        inputs = self.tokenizer(input_text, return_tensors="pt").to(self.model.device)
        output = self.model.generate(
            **inputs,
            max_length=self.max_length,
            temperature=self.temperature,
            top_p=self.top_p
        )
        return self.tokenizer.decode(output[0], skip_special_tokens=True)
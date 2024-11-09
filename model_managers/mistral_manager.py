# loads and manages Mistral models

# models/mistral_manager.py
import yaml
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


class MistralModel:
    def __init__(self, config_path="../configs/model_config.yaml"):
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)
        
        # Extract model-specific settings from config
        model_name = config['models']['mistral']['model_name']
        tokenizer_name = config['models']['mistral']['tokenizer_name']
        self.max_length = config['models']['mistral']['max_length']
        self.temperature = config['models']['mistral']['temperature']
        self.top_p = config['models']['mistral']['top_p']
        
        # Load tokenizer and model
        self.tokenizer = AutoTokenizer.from_pretrained(tokenizer_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.model.to(config['models']['mistral']['device'])
        

    def generate(self, input_text):
        inputs = self.tokenizer(input_text, return_tensors="pt").to(self.model.device)
        output = self.model.generate(
            **inputs,
            max_length=self.max_length,
            temperature=self.temperature,
            top_p=self.top_p
        )
        return self.tokenizer.decode(output[0], skip_special_tokens=True)
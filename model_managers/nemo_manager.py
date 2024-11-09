# Interface for NVIDIA’s NeMo models

# models/nemo_manager.py
import yaml
from nemo.collections.nlp.models.language_modeling import MegatronGPTModel


class NeMoModel:
    def __init__(self, config_path="../configs/model_config.yaml"):
        with open(config_path, "r") as file:
            config = yaml.safe_load(file)
        
        model_name = config['models']['nemo']['model_name']
        checkpoint_path = config['models']['nemo']['checkpoint_path']
        self.max_length = config['models']['nemo']['max_length']
        self.temperature = config['models']['nemo']['temperature']
        
        # Load NeMo model from a checkpoint if provided
        self.model = MegatronGPTModel.from_pretrained(model_name, checkpoint_path)
        self.model.eval()


    def generate(self, input_text):
        response = self.model.generate(input_text, max_length=self.max_length, temperature=self.temperature)
        return response
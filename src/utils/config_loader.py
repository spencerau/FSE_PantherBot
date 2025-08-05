import os
import yaml


def get_project_root():
    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    if os.path.exists(os.path.join(current_dir, "configs")):
        return current_dir
    
    if os.path.exists("/app/configs"):
        return "/app"
    
    return os.getcwd()

def load_config(config_name="config.yaml"):
    project_root = get_project_root()
    config_path = os.path.join(project_root, "configs", config_name)
    
    try:
        with open(config_path, 'r') as file:
            config = yaml.safe_load(file)
        
        # Override with environment variables if they exist
        if 'QDRANT_HOST' in os.environ:
            config['qdrant']['host'] = os.environ['QDRANT_HOST']
        
        if 'OLLAMA_HOST' in os.environ:
            config['embedding']['ollama_host'] = os.environ['OLLAMA_HOST']
            config['llm']['ollama_host'] = os.environ.get('OLLAMA_HOST', config['embedding']['ollama_host'])
        
        return config
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found: {config_path}")
    except yaml.YAMLError as e:
        raise Exception(f"Error parsing YAML file: {e}")
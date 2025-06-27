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
            return yaml.safe_load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found: {config_path}")
    except yaml.YAMLError as e:
        raise Exception(f"Error parsing YAML file: {e}")
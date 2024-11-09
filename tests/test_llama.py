# tests/test_llama.py

# Ensure the project root directory is in the path to locate `models`
import sys
from pathlib import Path

# Dynamically add the project root directory to `sys.path`
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

# Import the LLaMAModel class
from models.llama_manager import LLaMAModel

def test_llama_generation():
    # Initialize the model
    llama = LLaMAModel(config_path="configs/model_config.yaml")

    # Test input
    test_input = "Once upon a time"
    
    # Generate output
    output = llama.generate(test_input)
    
    # Print results
    print("Input:", test_input)
    print("Output:", output)

# Run the test if this script is executed directly
if __name__ == "__main__":
    test_llama_generation()
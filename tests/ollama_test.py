# tests/ollama_test.py
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from model_managers.llama_manager import LLaMAModel

#print pwd
print(os.getcwd())


def chat_with_model():
    #llama_model = LLaMAModel(config_path="/configs/model_config.yaml")
    llama_model = LLaMAModel(config_path=os.path.join(os.getcwd(), "configs", "model_config.yaml"))

    print("\nWelcome to the LLaMA Chat! Type 'exit' to end the session.")
    
    while True:
        user_input = input("\nUser: ")
        
        if user_input.lower() == "exit":
            print("Ending chat session. Goodbye!")
            break

        print("\nLLaMA:", end=" ", flush=True)
        for chunk in llama_model.stream_generate(user_input):
            print(chunk, end="", flush=True)
        print() 

if __name__ == "__main__":
    chat_with_model()
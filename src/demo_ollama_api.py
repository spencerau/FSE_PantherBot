#!/usr/bin/env python3
"""
Demo script showing different Ollama API modes for thinking
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils.ollama_api import get_ollama_api
from utils.config_loader import load_config


def demo_thinking_modes():
    """Demonstrate different thinking modes"""
    
    # Load configuration to get model name
    config = load_config()
    api = get_ollama_api()
    model = config.get('llm', {}).get('model', 'gemma3:4b')  # Default fallback if config not found
    
    if not api.check_model(model):
        print(f"Model {model} not available. Please install it first:")
        print(f"   ollama pull {model}")
        return
    
    question = "What is the capital of France and why is it important?"
    messages = [{"role": "user", "content": question}]
    
    print(f"🤔 Question: {question}\n")
    
    # Mode 1: No thinking
    print("=" * 60)
    print("MODE 1: No Thinking (think=False)")
    print("=" * 60)
    response = api.chat(model, messages, stream=False, think=False)
    print(response)
    
    # Mode 2: Thinking enabled but hidden
    print("\n" + "=" * 60)
    print("MODE 2: Thinking Enabled but Hidden (think=True, hide_thinking=True)")
    print("=" * 60)
    response = api.chat(model, messages, stream=False, think=True, hide_thinking=True)
    print(response)
    
    # Mode 3: Thinking visible
    print("\n" + "=" * 60)
    print("MODE 3: Thinking Visible (think=True, hide_thinking=False)")
    print("=" * 60)
    response = api.chat(model, messages, stream=False, think=True, hide_thinking=False)
    print(response)
    
    # Mode 4: Explicit thinking extraction
    print("\n" + "=" * 60)
    print("MODE 4: Explicit Thinking Extraction")
    print("=" * 60)
    result = api.chat_with_thinking(model, messages, stream=False)
    print("THINKING PROCESS:")
    print(result['thinking'])
    print("\nFINAL RESPONSE:")
    print(result['content'])


def demo_streaming():
    """Demonstrate streaming responses"""
    
    config = load_config()
    api = get_ollama_api()
    model = config.get('llm', {}).get('model', 'gemma3:4b')
    
    question = "Explain quantum computing in simple terms"
    messages = [{"role": "user", "content": question}]
    
    print(f"\n{'='*60}")
    print("STREAMING DEMO (with hidden thinking)")
    print("="*60)
    print(f"Question: {question}\n")
    
    print("Response (streaming):")
    for chunk in api.chat_stream(model, messages, think=True, hide_thinking=True):
        print(chunk, end='', flush=True)
    
    print("\n\nStreaming complete!")


if __name__ == "__main__":
    print("Ollama API Thinking Mode Demo")
    print("=" * 60)
    
    demo_thinking_modes()
    demo_streaming()
    
    print("\nDemo complete!")
    print("\nKey benefits of the new API:")
    print("• Fast GPU utilization on Mac M1/M2")
    print("• Thinking mode for better reasoning")
    print("• Hidden thinking for clean user experience")
    print("• Streaming for responsive UX")
    print("• Persistent connections for speed")

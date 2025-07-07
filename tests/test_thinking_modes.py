#!/usr/bin/env python3
"""
Test script for the new thinking mode and streaming features
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from retrieval.unified_rag import UnifiedRAG
from retrieval.rag_agent import RAGAgent


def test_all_modes():
    """Test all combinations of thinking and streaming modes"""
    
    print("🧪 Testing all thinking and streaming modes")
    print("=" * 60)
    
    rag = UnifiedRAG()
    agent = RAGAgent(rag)
    
    query = "What are the core requirements for Computer Science?"
    program = "cs"
    year = "2023"
    
    test_configs = [
        {"enable_thinking": False, "show_thinking": False, "use_streaming": False, "name": "No Thinking, No Stream"},
        {"enable_thinking": True, "show_thinking": False, "use_streaming": False, "name": "Hidden Thinking, No Stream"},
        {"enable_thinking": True, "show_thinking": True, "use_streaming": False, "name": "Visible Thinking, No Stream"},
        {"enable_thinking": False, "show_thinking": False, "use_streaming": True, "name": "No Thinking, Streaming"},
        {"enable_thinking": True, "show_thinking": False, "use_streaming": True, "name": "Hidden Thinking, Streaming"},
        {"enable_thinking": True, "show_thinking": True, "use_streaming": True, "name": "Visible Thinking, Streaming"},
    ]
    
    for i, config in enumerate(test_configs, 1):
        print(f"\nTest {i}: {config['name']}")
        print("-" * 40)
        
        try:
            answer, context, chunks = agent.answer(
                query, program, year,
                enable_thinking=config["enable_thinking"],
                show_thinking=config["show_thinking"],
                use_streaming=config["use_streaming"]
            )
            
            if config["use_streaming"] and hasattr(answer, '__iter__') and not isinstance(answer, str):
                print("📡 Streaming response:")
                full_response = ""
                chunk_count = 0
                for chunk in answer:
                    full_response += chunk
                    chunk_count += 1
                    if chunk_count <= 5:  # Show first 5 chunks
                        print(f"  Chunk {chunk_count}: '{chunk[:30]}{'...' if len(chunk) > 30 else ''}''")
                
                print(f"Streaming complete! Total response length: {len(full_response)}")
                
                # Check for thinking tags
                if "<think>" in full_response:
                    print(f"🧠 Thinking visible: Yes")
                else:
                    print(f"🧠 Thinking visible: No")
                    
            else:
                print(f"📄 Non-streaming response length: {len(answer)}")
                if "<think>" in answer:
                    print(f"🧠 Thinking visible: Yes")
                else:
                    print(f"🧠 Thinking visible: No")
            
            print(f"📚 Retrieved chunks: {len(chunks)}")
            
        except Exception as e:
            print(f"Error: {e}")
    
    print(f"\nAll tests completed!")


def test_streamlit_integration():
    """Test that the settings work as expected for Streamlit integration"""
    
    print("\n🖥️  Testing Streamlit Integration Scenarios")
    print("=" * 60)
    
    rag = UnifiedRAG()
    agent = RAGAgent(rag)
    
    # Simulate Streamlit session state values
    streamlit_scenarios = [
        {"enable_thinking": True, "show_thinking": False, "use_streaming": True, "scenario": "Default Production"},
        {"enable_thinking": False, "show_thinking": False, "use_streaming": True, "scenario": "Fast Mode"},
        {"enable_thinking": True, "show_thinking": True, "use_streaming": False, "scenario": "Debug Mode"},
    ]
    
    for scenario in streamlit_scenarios:
        print(f"\nScenario: {scenario['scenario']}")
        print("-" * 30)
        
        answer, context, chunks = agent.answer(
            "What math courses are required?", "cs", "2023",
            enable_thinking=scenario["enable_thinking"],
            show_thinking=scenario["show_thinking"],
            use_streaming=scenario["use_streaming"]
        )
        
        if scenario["use_streaming"] and hasattr(answer, '__iter__') and not isinstance(answer, str):
            # Simulate how Streamlit would handle streaming
            response_parts = list(answer)
            full_response = "".join(response_parts)
            print(f"Streamlit streaming simulation: {len(response_parts)} chunks, {len(full_response)} chars")
        else:
            print(f"Streamlit static response: {len(answer)} chars")


if __name__ == "__main__":
    test_all_modes()
    test_streamlit_integration()

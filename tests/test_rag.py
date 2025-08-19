import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from retrieval.unified_rag import UnifiedRAG
from utils.config_loader import load_config
from utils.ollama_api import get_ollama_api

def simple_ollama_llm(prompt, context):
    config = load_config()
    model = config.get('llm', {}).get('model', 'gemma3:4b')
    ollama_api = get_ollama_api()
    
    full_prompt = f"""Context: {context}

Question: {prompt}

Answer based on the context provided:"""
    
    try:
        response = ollama_api.chat(
            model=model,
            messages=[{'role': 'user', 'content': full_prompt}]
        )
        return response
    except Exception as e:
        return f"Error generating response: {str(e)}"


def test_rag_pipeline_real():
    rag_system = UnifiedRAG()
    
    queries = [
        "What are the graduation requirements for a Computer Science major who started in 2023?",
        "What are the prerequisites for CPSC 350 Data Structures and Algorithms?",
        "What are some upper division requirements for a Computer Science major?"
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"\n{'='*60}")
        print(f"TEST QUERY {i}: {query}")
        print('='*60)
        
        try:
            answer, context_chunks = rag_system.answer_question(
                query,
                student_program="Computer Science",  # Add student context for better routing
                student_year="2023",
                enable_reranking=False,  # Use faster mode for tests
                use_streaming=False,     # Return string instead of generator
                routing_method="hybrid"  # Use the new routing system
            )
            
            print(f"\nANSWER:")
            print(f"{answer}")
            
            print(f"\nCONTEXT SOURCES ({len(context_chunks)} chunks):")
            for j, chunk in enumerate(context_chunks[:5]):
                metadata = chunk.get('metadata', {})
                collection = chunk.get('collection', 'unknown')
                score = chunk.get('score', 0)
                text_preview = chunk.get('text', '')[:100] + "..." if len(chunk.get('text', '')) > 100 else chunk.get('text', '')
                
                print(f"  {j+1}. Collection: {collection}, Score: {score:.3f}")
                print(f"     Preview: {text_preview}")
            
            print(f"\nCOLLECTION BREAKDOWN:")
            collection_counts = {}
            for chunk in context_chunks:
                collection = chunk.get('collection', 'unknown')
                collection_counts[collection] = collection_counts.get(collection, 0) + 1
            
            for collection, count in collection_counts.items():
                print(f"  - {collection}: {count} chunks")
            
            assert isinstance(answer, str), "Answer should be a string"
            assert len(answer) > 0, "Answer should not be empty"
            assert isinstance(context_chunks, list), "Context should be a list"
            assert len(context_chunks) > 0, "Should have retrieved some chunks"
            
        except Exception as e:
            print(f"\nERROR: {str(e)}")
            raise e
    
    print(f"\n{'='*60}")
    print("ALL RAG TESTS COMPLETED SUCCESSFULLY!")
    print('='*60)

def test_unified_rag_basic():
    rag_system = UnifiedRAG()
    
    query = "What is Computer Science?"
    answer, context_chunks = rag_system.answer_question(
        query,
        student_program="Computer Science",
        student_year="2024", 
        enable_reranking=False,  # Use faster mode for tests
        use_streaming=False,     # Return string instead of generator
        routing_method="hybrid"  # Use new routing
    )
    result = {"answer": answer, "context": context_chunks}
    
    assert isinstance(result, dict), "Result should be a dictionary"
    assert 'answer' in result, "Result should contain an answer"
    assert 'context' in result, "Result should contain context"
    assert isinstance(result['answer'], str), "Answer should be a string"
    assert isinstance(result['context'], list), "Context should be a list"
    
    print(f"Basic RAG test passed")
    print(f"Query: {query}")
    print(f"Answer length: {len(result['answer'])} characters")
    print(f"Context chunks: {len(result['context'])}")

def test_unified_rag_collections():
    rag_system = UnifiedRAG()
    
    test_cases = [
        ("What are the Computer Science major requirements?", ["major_catalogs"]),
        ("What courses are offered this semester?", ["course_listings"]),
        ("What is the Analytics minor?", ["minor_catalogs"])
    ]
    
    for query, expected_collections in test_cases:
        answer, context_chunks = rag_system.answer_question(
            query, 
            enable_reranking=False,  # Use faster mode for tests
            use_streaming=False      # Return string instead of generator
        )
        result = {"answer": answer, "context": context_chunks}
        
        assert len(result['context']) > 0, f"No context retrieved for query: {query}"
        
        found_collections = set()
        for chunk in result['context']:
            if isinstance(chunk, dict) and 'collection' in chunk:
                found_collections.add(chunk['collection'])
        
        print(f"Query: {query}")
        print(f"Expected collections: {expected_collections}")
        print(f"Found collections: {list(found_collections)}")
        
        assert any(expected in found_collections for expected in expected_collections), \
            f"None of expected collections {expected_collections} found in {found_collections}"


def test_4_year_plans_rag():
    rag_system = UnifiedRAG()
    
    test_cases = [
        ("What courses should I take in my first year as a Computer Science major?", "cs"),
        ("Show me the 4-year plan for Computer Engineering", "ce"),
        ("What is the recommended course sequence for Software Engineering?", "se")
    ]
    
    for query, program in test_cases:
        print(f"\n{'='*50}")
        print(f"Testing 4-year plans: {query}")
        print(f"Program: {program}")
        print('='*50)
        
        answer, context_chunks = rag_system.answer_question(
            query,
            student_program=program,
            enable_reranking=False,  # Use faster mode for tests
            use_streaming=False      # Return string instead of generator
        )
        
        assert isinstance(answer, str), "Answer should be a string"
        assert len(answer) > 0, "Answer should not be empty"
        assert len(context_chunks) > 0, "Should have retrieved context chunks"
        
        # Check if 4_year_plans collection is included
        collections_found = set()
        for chunk in context_chunks:
            collection = chunk.get('collection', 'unknown')
            collections_found.add(collection)
        
        print(f"Collections found: {list(collections_found)}")
        print(f"Answer length: {len(answer)} characters")
        print(f"Context chunks: {len(context_chunks)}")
        
        # Should find some relevant collections (4_year_plans or major_catalogs)
        relevant_collections = {"4_year_plans", "major_catalogs"}
        has_relevant = any(col in collections_found for col in relevant_collections)
        assert has_relevant, f"No relevant collections found. Expected one of {relevant_collections}, got {collections_found}"
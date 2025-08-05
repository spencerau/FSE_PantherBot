#!/usr/bin/env python3
"""
Test script to verify source distribution across collections and metadata matching
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from retrieval.unified_rag import UnifiedRAG
from retrieval.rag_agent import RAGAgent
from collections import defaultdict


def test_source_distribution():
    """Test how sources are distributed across collections"""
    
    print("Testing Source Distribution Across Collections")
    print("=" * 70)
    
    rag = UnifiedRAG()
    agent = RAGAgent(rag)
    
    test_queries = [
        "What are the Computer Science major requirements?",
        "What math courses do I need?", 
        "What minors are available?",
        "Tell me about Chapman University"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\nQuery {i}: '{query}'")
        print("-" * 50)
        
        try:
            answer, context, chunks = agent.answer(
                query, "cs", "2023", 
                top_k=8, rerank_top_k=5,
                enable_thinking=False, use_streaming=False
            )
            
            # Analyze collection distribution
            collection_counts = defaultdict(int)
            metadata_analysis = {}
            
            for chunk in chunks:
                collection = chunk.get('collection', 'unknown')
                collection_counts[collection] += 1
                
                # Analyze metadata for program/year matching
                metadata = chunk.get('metadata', {})
                program = metadata.get('program', 'N/A')
                year = metadata.get('year', 'N/A')
                
                if collection not in metadata_analysis:
                    metadata_analysis[collection] = {'programs': set(), 'years': set()}
                
                if program != 'N/A':
                    metadata_analysis[collection]['programs'].add(program)
                if year != 'N/A':
                    metadata_analysis[collection]['years'].add(year)
            
            print(f"Collection Distribution:")
            for collection, count in collection_counts.items():
                print(f"  {collection}: {count} chunks")
                
                if collection in metadata_analysis:
                    programs = metadata_analysis[collection]['programs']
                    years = metadata_analysis[collection]['years']
                    print(f"    Programs: {programs if programs else 'None'}")
                    print(f"    Years: {years if years else 'None'}")
            
            print(f"Total chunks: {len(chunks)}")
            
        except Exception as e:
            print(f"Error: {e}")


def test_metadata_filtering():
    """Test metadata filtering for specific program and year"""
    
    print("\n\nTesting Metadata Filtering")
    print("=" * 70)
    
    rag = UnifiedRAG()
    
    # Test direct collection search with filters
    test_cases = [
        {"program": "cs", "year": "2023", "description": "CS 2023"},
        {"program": "ee", "year": "2022", "description": "EE 2022"},
        {"program": None, "year": None, "description": "No filters"},
    ]
    
    query = "Computer Science requirements"
    
    for case in test_cases:
        print(f"\nTest Case: {case['description']}")
        print("-" * 30)
        
        for collection_type in ['major_catalogs', 'minor_catalogs', 'course_listings']:
            collection_name = rag.collections[collection_type]
            
            results = rag.search_collection(
                query, collection_name, 
                case['program'], case['year'], top_k=3
            )
            
            print(f"  {collection_type}: {len(results)} results")
            
            for i, result in enumerate(results):
                metadata = result['metadata']
                program = metadata.get('program', 'N/A')
                year = metadata.get('year', 'N/A')
                file_name = metadata.get('file_name', 'N/A')
                score = result['score']
                
                print(f"    Result {i+1}: score={score:.3f}, program={program}, year={year}")
                print(f"      File: {file_name}")


def test_current_logic():
    """Test the current keyword-based collection selection logic"""
    
    print("\n\nTesting Current Collection Selection Logic")
    print("=" * 70)
    
    rag = UnifiedRAG()
    
    test_queries = [
        {"query": "What major requirements do I need?", "expected": ["general_knowledge", "major_catalogs"]},
        {"query": "What minors are available?", "expected": ["general_knowledge", "minor_catalogs"]},
        {"query": "What courses are offered this semester?", "expected": ["general_knowledge", "course_listings"]},
        {"query": "Tell me about Chapman University", "expected": ["general_knowledge", "major_catalogs", "minor_catalogs", "course_listings"]},
        {"query": "I need help with my degree program requirements", "expected": ["general_knowledge", "major_catalogs"]},
    ]
    
    for test in test_queries:
        print(f"\nQuery: '{test['query']}'")
        
        # Simulate the logic from answer_question
        collections_to_search = []
        collections_to_search.append(rag.collections['general_knowledge'])
        
        major_keywords = ['major', 'degree', 'program', 'graduation', 'requirement']
        if any(keyword in test['query'].lower() for keyword in major_keywords):
            collections_to_search.append(rag.collections['major_catalogs'])
        
        minor_keywords = ['minor']
        if any(keyword in test['query'].lower() for keyword in minor_keywords):
            collections_to_search.append(rag.collections['minor_catalogs'])
        
        course_keywords = ['course', 'class', 'schedule', 'credit', 'prerequisite']
        if any(keyword in test['query'].lower() for keyword in course_keywords):
            collections_to_search.append(rag.collections['course_listings'])
        
        # If only general_knowledge, search all
        if len(collections_to_search) == 1:
            collections_to_search = list(rag.collections.values())
        
        selected_collections = [name for name in collections_to_search]
        print(f"  Selected collections: {selected_collections}")
        
        # Calculate top_k per collection
        top_k = 8
        top_k_per_collection = max(1, top_k // len(collections_to_search))
        print(f"  top_k_per_collection: {top_k_per_collection}")


if __name__ == "__main__":
    test_source_distribution()
    test_metadata_filtering()
    test_current_logic()

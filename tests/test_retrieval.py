import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from retrieval.unified_rag import UnifiedRAG


def test_retrieval_by_year():
    rag_system = UnifiedRAG()
    
    test_cases = [
        ("Computer Science requirements", "2024"),
        ("Computer Science requirements", "2024")
    ]
    
    for query, year in test_cases:
        results = rag_system.search_collection(
            query=query,
            collection_name="major_catalogs",
            top_k=5,
            student_year=year
        )
        
        assert len(results) > 0, f"No results for year {year}"
        
        print(f"Year {year}: {len(results)} results")
        for result in results[:3]:
            metadata = result.get('metadata', {})
            result_year = metadata.get('year', 'Unknown')
            print(f"Document year: {result_year}")


def test_retrieval_by_major():
    rag_system = UnifiedRAG()
    
    majors = ["cs", "ce", "se"]  # Use program codes instead of full names
    major_names = ["Computer Science", "Computer Engineering", "Software Engineering"]
    
    for major, major_name in zip(majors, major_names):
        results = rag_system.search_collection(
            query=f"{major_name} requirements",
            collection_name="major_catalogs",
            top_k=5,
            student_program=major
        )
        
        print(f"Major {major_name}: {len(results)} results")
        for result in results[:3]:
            metadata = result.get('metadata', {})
            subject = metadata.get('subject', 'Unknown')
            print(f"  Document subject: {subject}")


def test_retrieval_by_minor():
    rag_system = UnifiedRAG()
    
    minors = ["Computer Science", "Analytics", "Computer Engineering"]
    
    for minor in minors:
        results = rag_system.search_collection(
            query=f"{minor} minor requirements",
            collection_name="minor_catalogs",
            top_k=3,
            student_program=minor
        )
        
        print(f"Minor {minor}: {len(results)} results")
        if len(results) > 0:
            for result in results[:2]:
                metadata = result.get('metadata', {})
                subject = metadata.get('subject', 'Unknown')
                program_type = metadata.get('program_type', 'Unknown')
                print(f"  Document: {subject} ({program_type})")


def test_retrieval_by_program_type():
    rag_system = UnifiedRAG()
    
    test_cases = [
        ("major_catalogs", "Computer Science major requirements"),
        ("minor_catalogs", "Analytics minor requirements")
    ]
    
    for collection, query in test_cases:
        results = rag_system.search_collection(
            query=query,
            collection_name=collection,
            top_k=5
        )
        
        assert len(results) > 0, f"No results for collection {collection}"
        
        print(f"Collection {collection}: {len(results)} results")
        for result in results[:3]:
            metadata = result.get('metadata', {})
            program_type = metadata.get('document_type', 'Unknown')
            subject = metadata.get('subject', 'Unknown')
            print(f"  {subject} ({program_type})")


def test_combined_student_filters():
    rag_system = UnifiedRAG()
    
    test_cases = [
        {
            "program": "cs",
            "year": "2024",
            "query": "graduation requirements",
            "collection": "major_catalogs"
        },
        {
            "program": "ds", 
            "year": "2024",
            "query": "degree requirements",
            "collection": "major_catalogs"
        }
    ]
    
    for case in test_cases:
        results = rag_system.search_collection(
            query=case["query"],
            collection_name=case["collection"],
            student_program=case["program"],
            student_year=case["year"],
            top_k=5
        )
        
        assert len(results) > 0, f"No results for {case['program']} {case['year']}"
        
        print(f"Student: {case['year']} {case['program']}")
        print(f"Results: {len(results)}")
        
        for result in results[:3]:
            metadata = result.get('metadata', {})
            year = metadata.get('year', 'Unknown')
            subject = metadata.get('subject', 'Unknown')
            score = result.get('score', 0)
            print(f"  {subject} ({year}) - Score: {score:.3f}")


def test_student_profile_retrieval():
    rag_system = UnifiedRAG()
    
    student_profiles = [
        {
            "year": "2024",
            "major": "Computer Science",
            "program_code": "cs",
            "query": "What are my graduation requirements?"
        },
        {
            "year": "2024", 
            "major": "Software Engineering",
            "program_code": "se",
            "query": "What programming courses are required?"
        },
        {
            "year": "2024",
            "major": "Data Science",
            "program_code": "ds", 
            "query": "What are the graduation requirements for my major?"
        }
    ]
    
    for profile in student_profiles:
        print(f"\nTesting student: {profile['year']} {profile['major']}")
        
        answer, context_chunks = rag_system.answer_question(
            profile['query'],
            student_program=profile['program_code'],
            student_year=profile['year']
        )
        
        assert isinstance(answer, str), "Answer should be a string"
        assert len(answer) > 0, "Answer should not be empty"
        assert len(context_chunks) > 0, "Should have retrieved context chunks"
        
        year_matches = sum(1 for chunk in context_chunks 
                          if chunk.get('metadata', {}).get('year') == profile['year'])
        major_matches = sum(1 for chunk in context_chunks 
                           if chunk.get('metadata', {}).get('subject') == profile['major'])
        
        print(f"Year matches: {year_matches}/{len(context_chunks)}")
        print(f"Major matches: {major_matches}/{len(context_chunks)}")
        print(f"Answer length: {len(answer)} characters")


def test_metadata_accuracy():
    rag_system = UnifiedRAG()
    
    results = rag_system.search_collection(
        query="Computer Science requirements",
        collection_name="major_catalogs", 
        student_program="cs",
        student_year="2024",
        top_k=10
    )
    
    assert len(results) > 0, "Should retrieve documents"
    
    cs_matches = 0
    year_matches = 0
    
    for result in results:
        metadata = result.get('metadata', {})
        subject = metadata.get('subject', '')
        year = metadata.get('year', '')
        
        if 'Computer Science' in subject:
            cs_matches += 1
        if year == '2024':
            year_matches += 1
    
    print(f"CS subject matches: {cs_matches}/{len(results)}")
    print(f"2024 year matches: {year_matches}/{len(results)}")
    
    assert cs_matches > 0, "Should find Computer Science documents"

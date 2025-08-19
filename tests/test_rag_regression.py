import pytest
import yaml
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from retrieval.unified_rag import UnifiedRAG
from utils.config_loader import load_config


@pytest.fixture
def rag_system():
    return UnifiedRAG()


@pytest.fixture
def test_queries():
    test_file = Path(__file__).parent / '../configs' / 'test_queries.yaml'
    with open(test_file, 'r') as f:
        data = yaml.safe_load(f)
    return data['queries']


@pytest.mark.parametrize("query_data", 
    yaml.safe_load(open(Path(__file__).parent / '../configs' / 'test_queries.yaml'))['queries'],
    ids=lambda q: f"{q.get('year', 'null')}_{q['major_or_minor']}_{q.get('major', 'general')}"
)
def test_rag_regression(rag_system, query_data):
    query = query_data['question']
    year = query_data.get('year')
    major = query_data.get('major')
    must_contain = query_data.get('must_contain', [])
    must_cite = query_data.get('must_cite_substring', [])
    expected_collections = query_data.get('expected_collections', [])
    
    # Convert major names to program codes if needed
    program_mappings = {
        'Computer Science': 'cs',
        'Computer Engineering': 'ce', 
        'Software Engineering': 'se',
        'Electrical Engineering': 'ee',
        'Data Science': 'ds'
    }
    program_code = program_mappings.get(major, major) if major else None
    
    answer, chunks = rag_system.answer_question(
        query,
        student_program=program_code,  # Use program code instead of full name
        student_year=year,
        use_streaming=False,
        enable_reranking=False,  # Use faster mode for tests
        routing_method="hybrid"  # Use new routing system
    )
    
    if isinstance(answer, str):
        answer_text = answer
    else:
        answer_text = str(answer)
    
    # Check required content
    for required_term in must_contain:
        assert required_term.lower() in answer_text.lower(), \
            f"Answer should contain '{required_term}' for query: {query}"
    
    # Check citations in chunks
    citation_found = True
    for citation_term in must_cite:
        found_in_chunks = any(
            citation_term.lower() in chunk.get('text', '').lower()
            for chunk in chunks
        )
        if not found_in_chunks:
            citation_found = False
            break
    
    assert citation_found, \
        f"Expected citation terms {must_cite} not found in retrieved chunks for query: {query}"
    
    if expected_collections:
        collections_found = set(chunk.get('collection', 'unknown') for chunk in chunks)
        found_expected = any(expected in collections_found for expected in expected_collections)
        assert found_expected, \
            f"Expected collections {expected_collections} but got {list(collections_found)} for query: {query}"
    
    assert len(chunks) > 0, f"No chunks retrieved for query: {query}"
    assert answer_text.strip() != "", f"Empty answer for query: {query}"


def test_2022_catalog_queries(rag_system, test_queries):
    year_2022_queries = [q for q in test_queries if q.get('year') == '2022']
    print(f"\nTesting {len(year_2022_queries)} queries for 2022...")
    
    for i, query_data in enumerate(year_2022_queries, 1):
        print(f"[{i}/{len(year_2022_queries)}] 2022: {query_data['question'][:60]}...")
        answer, chunks = rag_system.answer_question(
            query_data['question'],
            student_program=query_data.get('major'),
            student_year='2022',
            use_streaming=False,
            enable_reranking=False  # Use faster mode for tests
        )
        
        print(f"Chunks retrieved: {len(chunks)}")
        assert len(chunks) > 0, f"No chunks for 2022 query: {query_data['question']}"


def test_2023_catalog_queries(rag_system, test_queries):
    year_2023_queries = [q for q in test_queries if q.get('year') == '2023']
    print(f"\nTesting {len(year_2023_queries)} queries for 2023...")
    
    for i, query_data in enumerate(year_2023_queries, 1):
        print(f"[{i}/{len(year_2023_queries)}] 2023: {query_data['question'][:60]}...")
        answer, chunks = rag_system.answer_question(
            query_data['question'],
            student_program=query_data.get('major'),
            student_year='2023',
            use_streaming=False,
            enable_reranking=False  # Use faster mode for tests
        )
        
        print(f"Chunks retrieved: {len(chunks)}")
        assert len(chunks) > 0, f"No chunks for 2023 query: {query_data['question']}"


def test_2024_catalog_queries(rag_system, test_queries):
    year_2024_queries = [q for q in test_queries if q.get('year') == '2024']
    print(f"\nTesting {len(year_2024_queries)} queries for 2024...")
    
    for i, query_data in enumerate(year_2024_queries, 1):
        print(f"[{i}/{len(year_2024_queries)}] 2024: {query_data['question'][:60]}...")
        answer, chunks = rag_system.answer_question(
            query_data['question'],
            student_program=query_data.get('major'),
            student_year='2024',
            use_streaming=False,
            enable_reranking=False  # Use faster mode for tests
        )
        
        print(f"Chunks retrieved: {len(chunks)}")
        assert len(chunks) > 0, f"No chunks for 2024 query: {query_data['question']}"


def test_write_evaluation_report(rag_system, test_queries):
    results = []
    total_queries = len(test_queries)
    print(f"\nStarting evaluation of {total_queries} test queries...")
    
    for i, query_data in enumerate(test_queries, 1):
        print(f"[{i}/{total_queries}] Testing: {query_data['question'][:80]}...")
        print(f"Year: {query_data['year']}, Major: {query_data.get('major', 'N/A')}")
        
        try:
            start_time = time.time()
            
            answer, chunks = rag_system.answer_question(
                query_data['question'],
                student_program=query_data.get('major'),
                student_year=query_data['year'],
                use_streaming=False,
                test_mode=True,
                enable_reranking=False  # Use faster mode for tests
            )
            query_time = time.time() - start_time
            
            if isinstance(answer, str):
                answer_text = answer
            else:
                answer_text = str(answer)
            
            citation_check = all(
                any(term.lower() in chunk.get('text', '').lower() for chunk in chunks)
                for term in query_data.get('must_cite_substring', [])
            )
            
            result = {
                'query': query_data['question'],
                'year': query_data['year'],
                'major': query_data.get('major'),
                'answer_length': len(answer_text),
                'chunks_retrieved': len(chunks),
                'contains_check_passed': 'test mode' in answer_text.lower(),
                'citation_check_passed': citation_check,
                'overall_success': len(chunks) > 0 and citation_check,
                'timeout': False,
                'test_mode': True
            }
            
            print(f"Success: {result['overall_success']} | Chunks: {len(chunks)} | Time: {query_time:.1f}s | Test mode")
            
        except Exception as e:
            result = {
                'query': query_data['question'],
                'year': query_data['year'],
                'major': query_data.get('major'),
                'error': str(e),
                'overall_success': False,
                'timeout': 'timeout' in str(e).lower(),
                'test_mode': True
            }
            print(f"Error: {str(e)[:100]}")
        
        results.append(result)
    
    reports_dir = Path(__file__).parent.parent / '.reports'
    reports_dir.mkdir(exist_ok=True)
    
    with open(reports_dir / 'rag_eval.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    success_rate = sum(1 for r in results if r.get('overall_success', False)) / len(results)
    successful_queries = sum(1 for r in results if r.get('overall_success', False))
    timeout_queries = sum(1 for r in results if r.get('timeout', False))
    print(f"\nEvaluation Complete!")
    print(f"Success Rate: {success_rate:.2%} ({successful_queries}/{len(results)} queries)")
    print(f"Timeouts: {timeout_queries} queries")
    print(f"Report saved to: {reports_dir / 'rag_eval.json'}")
    
    assert success_rate > 0.3, f"Success rate too low: {success_rate:.2%}"


def test_retrieval_only_validation(rag_system, test_queries):
    print(f"\nTesting retrieval filtering for {len(test_queries)} queries...")
    retrieval_failures = []
    
    for i, query_data in enumerate(test_queries, 1):
        print(f"[{i}/{len(test_queries)}] Retrieval test: {query_data['question'][:60]}...")
        
        try:
            collections_to_search = ['major_catalogs']
            if 'minor' in query_data['question'].lower():
                collections_to_search.append('minor_catalogs')
            
            retrieved_chunks = rag_system.search_multiple_collections(
                query_data['question'], 
                collections_to_search,
                student_program=query_data.get('major'),
                student_year=query_data['year']
            )
            
            if not retrieved_chunks:
                retrieval_failures.append(f"No chunks for: {query_data['question']}")
                print(f"FAIL: No chunks retrieved")
                continue
                
            year_filter_ok = True
            program_filter_ok = True
            
            major_chunks = [c for c in retrieved_chunks if c.get('collection') == 'major_catalogs']
            if query_data.get('major') and major_chunks:
                program_mappings = {
                    'Computer Science': 'cs',
                    'Computer Engineering': 'ce',
                    'Software Engineering': 'se',
                    'Electrical Engineering': 'ee',
                    'Data Science': 'ds'
                }
                expected_program = program_mappings.get(query_data.get('major'), query_data.get('major').lower())
                
                for chunk in major_chunks:
                    if chunk['metadata'].get('program') != expected_program:
                        program_filter_ok = False
                        break
            
            for chunk in retrieved_chunks:
                chunk_year = chunk['metadata'].get('year')
                collection = chunk.get('collection', '')
                
                if chunk_year != query_data['year'] and collection not in ['general_knowledge']:
                    year_filter_ok = False
                    break
            
            if not year_filter_ok or not program_filter_ok:
                retrieval_failures.append(f"Filter issue for: {query_data['question']}")
            
            result_status = "PASS" if year_filter_ok and program_filter_ok else "FILTER_ISSUE"
            print(f"{result_status}: {len(retrieved_chunks)} chunks, Year: {year_filter_ok}, Program: {program_filter_ok}")
            
        except Exception as e:
            retrieval_failures.append(f"Error for {query_data['question']}: {str(e)}")
            print(f"ERROR: {str(e)[:50]}")
    
    print(f"\nRetrieval test complete. Failures: {len(retrieval_failures)}")
    for failure in retrieval_failures[:5]:
        print(f"  - {failure}")
    
    assert len(retrieval_failures) < len(test_queries) * 0.3, f"Too many retrieval failures: {len(retrieval_failures)}"


@pytest.mark.skipif(os.getenv("SKIP_SLOW_TESTS") == "1", reason="Slow test skipped")
def test_full_llm_evaluation(rag_system, test_queries):
    results = []
    total_queries = len(test_queries)
    print(f"\nStarting FULL LLM evaluation of {total_queries} test queries...")
    
    for i, query_data in enumerate(test_queries, 1):
        print(f"[{i}/{total_queries}] Full LLM test: {query_data['question'][:80]}...")
        print(f"Year: {query_data['year']}, Major: {query_data.get('major', 'N/A')}")
        
        try:
            start_time = time.time()
            answer, chunks = rag_system.answer_question(
                query_data['question'],
                student_program=query_data.get('major'),
                student_year=query_data['year'],
                use_streaming=False,
                test_mode=False,
                enable_reranking=False  # Use faster mode for tests
            )
            query_time = time.time() - start_time
            
            if isinstance(answer, str):
                answer_text = answer
            else:
                answer_text = str(answer)
            
            if not answer_text.strip() or query_time > 120:
                print(f"Timeout or empty response after {query_time:.1f}s")
                result = {
                    'query': query_data['question'],
                    'year': query_data['year'],
                    'major': query_data.get('major'),
                    'answer_length': len(answer_text),
                    'chunks_retrieved': len(chunks),
                    'contains_check_passed': False,
                    'citation_check_passed': len(chunks) > 0,
                    'overall_success': False,
                    'timeout': query_time > 120
                }
            else:
                contains_check = all(
                    term.lower() in answer_text.lower() 
                    for term in query_data.get('must_contain', [])
                )
                
                citation_check = all(
                    any(term.lower() in chunk.get('text', '').lower() for chunk in chunks)
                    for term in query_data.get('must_cite_substring', [])
                )
                
                result = {
                    'query': query_data['question'],
                    'year': query_data['year'],
                    'major': query_data.get('major'),
                    'answer_length': len(answer_text),
                    'chunks_retrieved': len(chunks),
                    'contains_check_passed': contains_check,
                    'citation_check_passed': citation_check,
                    'overall_success': contains_check and citation_check and len(chunks) > 0,
                    'timeout': False
                }
            
            print(f"Success: {result['overall_success']} | Chunks: {len(chunks)} | Answer: {len(answer_text)} chars | Time: {query_time:.1f}s")
            
        except Exception as e:
            result = {
                'query': query_data['question'],
                'year': query_data['year'],
                'major': query_data.get('major'),
                'error': str(e),
                'overall_success': False,
                'timeout': 'timeout' in str(e).lower()
            }
            print(f"Error: {str(e)[:100]}")
        
        results.append(result)
    
    reports_dir = Path(__file__).parent.parent / '.reports'
    reports_dir.mkdir(exist_ok=True)
    
    with open(reports_dir / 'rag_eval_full.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    success_rate = sum(1 for r in results if r.get('overall_success', False)) / len(results)
    successful_queries = sum(1 for r in results if r.get('overall_success', False))
    timeout_queries = sum(1 for r in results if r.get('timeout', False))
    print(f"\nFull LLM Evaluation Complete!")
    print(f"Success Rate: {success_rate:.2%} ({successful_queries}/{len(results)} queries)")
    print(f"Timeouts: {timeout_queries} queries")
    print(f"Report saved to: {reports_dir / 'rag_eval_full.json'}")
    
    assert success_rate > 0.3, f"Success rate too low: {success_rate:.2%}"

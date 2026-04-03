import json
import os
import re
import sys
import time
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fse_retrieval.fse_unified_rag import FSEUnifiedRAG as UnifiedRAG
from fse_utils.config_loader import load_config

def _build_program_map():
    cfg = load_config()
    domain = cfg.get('domain', {})
    m = {}
    m.update(domain.get('majors', {}))
    m.update(domain.get('minors', {}))
    return m

PROGRAM_MAP = _build_program_map()


@pytest.fixture
def rag_system():
    return UnifiedRAG()


@pytest.fixture
def test_queries():
    test_file = Path(__file__).parent / '../configs' / 'test_queries.yaml'
    with open(test_file, 'r') as f:
        data = yaml.safe_load(f)
    return data['queries']


def _query_id(q):
    year = q.get('year', 'null')
    if q.get('major') and q.get('minor'):
        return f"{year}_multi_{q['major']}+{q['minor']}"
    elif q.get('minor'):
        return f"{year}_minor_{q['minor']}"
    elif q.get('major'):
        return f"{year}_major_{q['major']}"
    return f"{year}_general"


def _answer_question(rag_system, query_data):
    major_code = PROGRAM_MAP.get(query_data['major'], query_data['major']) if query_data.get('major') else None
    minor_code = PROGRAM_MAP.get(query_data['minor']) if query_data.get('minor') else None

    result = rag_system.answer_question(
        query_data['question'],
        student_program=major_code,
        student_minor=minor_code,
        student_year=query_data.get('year'),
        stream=False,
        return_debug_info=True,
    )
    if isinstance(result, tuple):
        answer, sources, debug = result
    else:
        answer, sources, debug = result, [], {}
    return str(answer), sources, debug


def _llm_judge(question: str, answer: str, rubric: str, sample: str = None) -> tuple:
    from core_rag.utils.llm_api import get_intermediate_ollama_api

    cfg = load_config()
    model = cfg['intermediate_llm']['model']
    api = get_intermediate_ollama_api(timeout=cfg['intermediate_llm'].get('timeout', 60))

    sample_section = f"\nReference Answer:\n{sample}\n" if sample else ""
    prompt = (
        "You are evaluating an AI-generated academic advising answer.\n\n"
        f"Question: {question}\n\n"
        f"Generated Answer:\n{answer}\n"
        f"{sample_section}\n"
        f"Evaluation Criteria:\n{rubric}\n\n"
        "Does the generated answer satisfy the criteria? Be lenient about phrasing — "
        "reward correct information even if worded differently than the reference.\n"
        'Respond with JSON only: {"pass": true/false, "reason": "one sentence explanation"}'
    )

    raw = api.chat(
        model=model,
        messages=[{'role': 'user', 'content': prompt}],
        stream=False,
        think=True,
        hide_thinking=True,
        max_tokens=20000,
    )

    clean = re.sub(r'```(?:json)?\s*', '', raw).replace('```', '').strip()

    match = re.search(r'\{[^{}]*"pass"[^{}]*\}', clean, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            return bool(data.get('pass')), data.get('reason', '')
        except json.JSONDecodeError:
            pass

    pass_match = re.search(r'"pass"\s*:\s*(true|false)', clean, re.IGNORECASE)
    if pass_match:
        passed = pass_match.group(1).lower() == 'true'
        reason_match = re.search(r'"reason"\s*:\s*"([^"]*)', clean)  # closing quote optional for truncated JSON
        reason = reason_match.group(1) if reason_match else '(reason truncated)'
        return passed, reason

    return False, f"Judge returned unparseable response: {raw[:200]}"


@pytest.mark.integration
@pytest.mark.parametrize("query_data",
    yaml.safe_load(open(Path(__file__).parent / '../configs' / 'test_queries.yaml'))['queries'],
    ids=_query_id
)
def test_rag_regression(rag_system, query_data):
    answer_text, sources, debug = _answer_question(rag_system, query_data)

    assert len(sources) > 0, f"No sources retrieved for: {query_data['question']}"
    assert answer_text.strip() != "", f"Empty answer for: {query_data['question']}"

    expected_collections = query_data.get('expected_collections', [])
    if expected_collections:
        collections_found = {s.get('collection', 'unknown') for s in sources}
        assert any(e in collections_found for e in expected_collections), \
            f"Expected {expected_collections}, got {list(collections_found)} for: {query_data['question']}"

    acceptable_answer = query_data.get('acceptable_answer')
    sample_answer = query_data.get('sample_answer') or None
    if acceptable_answer:
        passed, reason = _llm_judge(
            query_data['question'], answer_text, acceptable_answer, sample_answer
        )
        assert passed, (
            f"LLM judge rejected answer for: {query_data['question']}\n"
            f"Reason: {reason}\n"
            f"Answer: {answer_text[:1500]}"
        )


@pytest.mark.integration
def test_2022_catalog_queries(rag_system, test_queries):
    for query_data in [q for q in test_queries if q.get('year') == '2022']:
        _, sources, _ = _answer_question(rag_system, query_data)
        assert len(sources) > 0, f"No sources for 2022 query: {query_data['question']}"


@pytest.mark.integration
def test_2023_catalog_queries(rag_system, test_queries):
    for query_data in [q for q in test_queries if q.get('year') == '2023']:
        _, sources, _ = _answer_question(rag_system, query_data)
        assert len(sources) > 0, f"No sources for 2023 query: {query_data['question']}"


@pytest.mark.integration
def test_2024_catalog_queries(rag_system, test_queries):
    for query_data in [q for q in test_queries if q.get('year') == '2024']:
        _, sources, _ = _answer_question(rag_system, query_data)
        assert len(sources) > 0, f"No sources for 2024 query: {query_data['question']}"


@pytest.mark.integration
def test_write_evaluation_report(rag_system, test_queries):
    results = []

    for query_data in test_queries:
        try:
            start = time.time()
            answer_text, sources, debug = _answer_question(rag_system, query_data)
            elapsed = time.time() - start

            judge_passed = None
            acceptable_answer = query_data.get('acceptable_answer')
            sample_answer = query_data.get('sample_answer') or None
            if acceptable_answer:
                judge_passed, _ = _llm_judge(
                    query_data['question'], answer_text, acceptable_answer, sample_answer
                )

            results.append({
                'query': query_data['question'],
                'year': query_data.get('year'),
                'major': query_data.get('major'),
                'answer_length': len(answer_text),
                'sources_retrieved': len(sources),
                'judge_passed': judge_passed,
                'overall_success': len(sources) > 0 and (judge_passed is not False),
                'elapsed_s': round(elapsed, 1),
            })
        except Exception as e:
            results.append({
                'query': query_data['question'],
                'year': query_data.get('year'),
                'major': query_data.get('major'),
                'error': str(e),
                'overall_success': False,
            })

    reports_dir = Path(__file__).parent.parent / '.reports'
    reports_dir.mkdir(exist_ok=True)
    with open(reports_dir / 'rag_eval.json', 'w') as f:
        json.dump(results, f, indent=2)

    success_rate = sum(1 for r in results if r.get('overall_success')) / len(results)
    assert success_rate > 0.3, f"Success rate too low: {success_rate:.2%}"


@pytest.mark.integration
def test_retrieval_only_validation(rag_system, test_queries):
    retrieval_failures = []

    for query_data in test_queries:
        try:
            program_code = PROGRAM_MAP.get(query_data.get('major'), query_data.get('major'))
            user_context = {}
            if program_code:
                user_context['program'] = program_code
            if query_data.get('year'):
                user_context['year'] = query_data['year']

            collections = ['major_catalogs']
            if 'minor' in query_data['question'].lower():
                collections.append('minor_catalogs')

            chunks = []
            for coll in collections:
                chunks.extend(rag_system.search_collection(
                    query_data['question'], coll, user_context or None, top_k=10
                ))

            if not chunks:
                retrieval_failures.append(f"No chunks for: {query_data['question']}")
        except Exception as e:
            retrieval_failures.append(f"Error for {query_data['question']}: {e}")

    assert len(retrieval_failures) < len(test_queries) * 0.3, \
        f"Too many retrieval failures: {len(retrieval_failures)}"


@pytest.mark.integration
@pytest.mark.skipif(os.getenv("SKIP_SLOW_TESTS") == "1", reason="Slow test skipped")
def test_full_llm_evaluation(rag_system, test_queries):
    results = []

    for query_data in test_queries:
        try:
            start = time.time()
            answer_text, sources, _ = _answer_question(rag_system, query_data)
            elapsed = time.time() - start

            judge_passed = None
            acceptable_answer = query_data.get('acceptable_answer')
            sample_answer = query_data.get('sample_answer') or None
            if acceptable_answer:
                judge_passed, judge_reason = _llm_judge(
                    query_data['question'], answer_text, acceptable_answer, sample_answer
                )
            else:
                judge_reason = None

            results.append({
                'query': query_data['question'],
                'year': query_data.get('year'),
                'major': query_data.get('major'),
                'answer_length': len(answer_text),
                'sources_retrieved': len(sources),
                'judge_passed': judge_passed,
                'judge_reason': judge_reason,
                'overall_success': len(sources) > 0 and (judge_passed is not False),
                'elapsed_s': round(elapsed, 1),
            })
        except Exception as e:
            results.append({
                'query': query_data['question'],
                'year': query_data.get('year'),
                'major': query_data.get('major'),
                'error': str(e),
                'overall_success': False,
            })

    reports_dir = Path(__file__).parent.parent / '.reports'
    reports_dir.mkdir(exist_ok=True)
    with open(reports_dir / 'rag_eval_full.json', 'w') as f:
        json.dump(results, f, indent=2)

    success_rate = sum(1 for r in results if r.get('overall_success')) / len(results)
    assert success_rate > 0.3, f"Success rate too low: {success_rate:.2%}"

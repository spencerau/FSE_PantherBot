"""
Full eval corpus test — runs all questions in configs/eval_corpus.yaml.

Unlike test_rag_regression.py, this file NEVER hard-asserts on judge pass/fail.
Every question runs to completion; results are recorded incrementally to
.reports/eval_corpus.json so cluster job interruptions don't lose progress.

Run locally:
    pytest tests/test_eval_corpus.py -m eval -v

Run on DGX (after setting DGX=true and starting vLLM + Docker containers):
    DGX=true pytest tests/test_eval_corpus.py -m eval -v
"""
import json
import os
import re
import sys
import time
from pathlib import Path

import pytest
import requests
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fse_retrieval.fse_unified_rag import FSEUnifiedRAG as UnifiedRAG
from fse_utils.config_loader import load_config

CORPUS_FILE = Path(__file__).parent.parent / 'configs' / 'eval_corpus.yaml'


def _build_program_map():
    cfg = load_config()
    domain = cfg.get('domain', {})
    m = {}
    m.update(domain.get('majors', {}))
    m.update(domain.get('minors', {}))
    return m


PROGRAM_MAP = _build_program_map()


def _load_corpus():
    if not CORPUS_FILE.exists():
        pytest.skip(f'eval_corpus.yaml not found — run scripts/build_eval_corpus.py first')
    with open(CORPUS_FILE) as f:
        data = yaml.safe_load(f)
    return [q for q in data.get('queries', []) if not str(q.get('question', '')).startswith('#')]


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
    """Returns (passed, reason, output_tokens, tokens_per_s)."""
    cfg = load_config()
    int_cfg = cfg['intermediate_llm']
    backend = cfg.get('backend', 'ollama')
    model = int_cfg['model']
    timeout = int_cfg.get('timeout', 60)
    host = int_cfg.get('host', 'localhost')
    port = int_cfg.get('port', 11434)

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
    messages = [{'role': 'user', 'content': prompt}]

    judge_start = time.time()
    output_tokens = None
    if backend in ('vllm', 'mlx'):
        url = f"http://{host}:{port}/v1/chat/completions"
        payload = {'model': model, 'messages': messages, 'stream': False, 'max_tokens': 20000,
                   'temperature': int_cfg.get('temperature', 0.1)}
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        raw = data['choices'][0]['message']['content'] or ''
        raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
        output_tokens = data.get('usage', {}).get('completion_tokens')
    else:
        url = f"http://{host}:{port}/api/chat"
        payload = {'model': model, 'messages': messages, 'stream': False, 'think': True}
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        raw = data.get('message', {}).get('content', '')
        raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
        output_tokens = data.get('eval_count')

    judge_elapsed = round(time.time() - judge_start, 1)
    tokens_per_s = round(output_tokens / judge_elapsed, 1) if output_tokens and judge_elapsed > 0 else None

    clean = re.sub(r'```(?:json)?\s*', '', raw).replace('```', '').strip()

    match = re.search(r'\{[^{}]*"pass"[^{}]*\}', clean, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            return bool(parsed.get('pass')), parsed.get('reason', ''), output_tokens, tokens_per_s
        except json.JSONDecodeError:
            pass

    pass_match = re.search(r'"pass"\s*:\s*(true|false)', clean, re.IGNORECASE)
    if pass_match:
        passed = pass_match.group(1).lower() == 'true'
        reason_match = re.search(r'"reason"\s*:\s*"([^"]*)', clean)
        reason = reason_match.group(1) if reason_match else '(reason truncated)'
        return passed, reason, output_tokens, tokens_per_s

    return False, f"Judge returned unparseable response: {raw[:200]}", output_tokens, tokens_per_s


@pytest.fixture(scope="module", autouse=True)
def _eval_report():
    """Clears eval_corpus.json at module start; yields append callback."""
    reports_dir = Path(__file__).parent.parent / '.reports'
    reports_dir.mkdir(exist_ok=True)
    report_file = reports_dir / 'eval_corpus.json'
    report_file.write_text('[]')
    results = []

    def append(record):
        results.append(record)
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2)

    yield append


@pytest.fixture(scope="module")
def rag_system():
    return UnifiedRAG()


@pytest.mark.eval
@pytest.mark.parametrize("query_data", _load_corpus(), ids=_query_id)
def test_eval_corpus(rag_system, query_data, _eval_report):
    """
    Eval-mode test: runs every question, records results to .reports/eval_corpus.json,
    then asserts on sources, collection routing, and judge verdict.
    """
    start = time.time()
    try:
        answer_text, sources, _ = _answer_question(rag_system, query_data)
        elapsed = round(time.time() - start, 1)

        judge_passed = None
        judge_reason = None
        judge_output_tokens = None
        judge_tokens_per_s = None
        acceptable_answer = query_data.get('acceptable_answer')
        sample_answer = query_data.get('sample_answer') or None
        if acceptable_answer:
            judge_passed, judge_reason, judge_output_tokens, judge_tokens_per_s = _llm_judge(
                query_data['question'], answer_text, acceptable_answer, sample_answer
            )

        expected_collections = query_data.get('expected_collections', [])
        collections_found = {s.get('collection', 'unknown') for s in sources}
        collection_ok = (
            not expected_collections
            or any(e in collections_found for e in expected_collections)
        )

        _eval_report({
            'query': query_data['question'],
            'year': query_data.get('year'),
            'major': query_data.get('major'),
            'minor': query_data.get('minor'),
            'answer': answer_text,
            'answer_length': len(answer_text),
            'answer_words': len(answer_text.split()),
            'sources_retrieved': len(sources),
            'collections_found': sorted(collections_found),
            'collection_ok': collection_ok,
            'judge_passed': judge_passed,
            'judge_reason': judge_reason,
            'judge_output_tokens': judge_output_tokens,
            'judge_tokens_per_s': judge_tokens_per_s,
            'overall_success': (
                len(sources) > 0
                and answer_text.strip() != ''
                and collection_ok
                and (judge_passed is not False)
            ),
            'elapsed_s': elapsed,
        })

        assert len(sources) > 0, f"No sources retrieved for: {query_data['question']}"
        assert answer_text.strip() != '', f"Empty answer for: {query_data['question']}"
        if expected_collections:
            assert collection_ok, \
                f"Expected {expected_collections}, got {sorted(collections_found)} for: {query_data['question']}"
        if acceptable_answer and judge_passed is not None:
            assert judge_passed, (
                f"LLM judge rejected answer for: {query_data['question']}\n"
                f"Reason: {judge_reason}\n"
                f"Answer: {answer_text[:1500]}"
            )
    except Exception as exc:
        elapsed = round(time.time() - start, 1)
        _eval_report({
            'query': query_data['question'],
            'year': query_data.get('year'),
            'major': query_data.get('major'),
            'minor': query_data.get('minor'),
            'error': str(exc),
            'overall_success': False,
            'elapsed_s': elapsed,
        })
        raise

"""
Complex/custom query eval — CS major, Game Dev minor, 2025 catalog year.

No LLM judge. Records elapsed time, approximate output tok/s, and the full
generated response for manual review.

Run locally:
    pytest tests/test_eval_complex.py -m eval -v

Run on DGX:
    DGX=true pytest tests/test_eval_complex.py -m eval -v
"""
import json
import os
import sys
import time
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from fse_retrieval.fse_unified_rag import FSEUnifiedRAG as UnifiedRAG
from fse_utils.config_loader import load_config

CORPUS_FILE = Path(__file__).parent.parent / 'configs' / 'eval_complex.yaml'
REPORT_FILE = Path(__file__).parent.parent / '.reports' / 'eval_complex.json'

PROGRAM_MAP = {}


def _build_program_map():
    global PROGRAM_MAP
    cfg = load_config()
    domain = cfg.get('domain', {})
    PROGRAM_MAP.update(domain.get('majors', {}))
    PROGRAM_MAP.update(domain.get('minors', {}))


def _load_corpus():
    if not CORPUS_FILE.exists():
        pytest.skip(f'eval_complex.yaml not found at {CORPUS_FILE}')
    with open(CORPUS_FILE) as f:
        data = yaml.safe_load(f)
    return [
        q for q in data.get('queries', [])
        if q.get('question') and q['question'] != 'PLACEHOLDER'
    ]


def _query_id(q):
    slug = q['question'][:60].replace(' ', '_').replace('?', '')
    return slug


@pytest.fixture(scope="module", autouse=True)
def _complex_report():
    _build_program_map()
    corpus = _load_corpus()
    meta = {k: corpus[0][k] for k in ('major', 'minor', 'year') if corpus and k in corpus[0]}
    REPORT_FILE.parent.mkdir(exist_ok=True)
    report = {**meta, 'results': []}
    REPORT_FILE.write_text(json.dumps(report, indent=2))
    results = []

    def append(record):
        results.append(record)
        with open(REPORT_FILE, 'w') as f:
            json.dump({**meta, 'results': results}, f, indent=2)

    yield append


@pytest.fixture(scope="module")
def rag_system():
    return UnifiedRAG()


@pytest.mark.eval
@pytest.mark.parametrize("query_data", _load_corpus(), ids=_query_id)
def test_eval_complex(rag_system, query_data, _complex_report):
    major_code = PROGRAM_MAP.get(query_data['major'], query_data['major']) if query_data.get('major') else None
    minor_code = PROGRAM_MAP.get(query_data['minor']) if query_data.get('minor') else None

    parts = []
    if query_data.get('major'):
        parts.append(f"major: {query_data['major']}")
    if query_data.get('minor'):
        parts.append(f"minor: {query_data['minor']}")
    if query_data.get('year'):
        parts.append(f"catalog year: {query_data['year']}")
    question = f"[Student context — {', '.join(parts)}]\n{query_data['question']}" if parts else query_data['question']

    start = time.time()
    result = rag_system.answer_question(
        question,
        student_program=major_code,
        student_minor=minor_code,
        student_year=query_data.get('year'),
        stream=False,
        return_debug_info=True,
    )
    elapsed = round(time.time() - start, 1)

    if isinstance(result, tuple):
        answer, sources, _ = result
    else:
        answer, sources, _ = result, [], {}

    answer = str(answer)

    _complex_report({
        'question': query_data['question'],
        'answer': answer,
        'answer_words': len(answer.split()),
        'sources_retrieved': len(sources),
        'collections_found': sorted({s.get('collection', 'unknown') for s in sources}),
        'elapsed_s': elapsed,
    })

#!/usr/bin/env python3
"""Quick summary of .reports/eval_corpus.json."""

import json
import sys
from pathlib import Path
from collections import defaultdict

import yaml

report = Path(__file__).parent.parent / '.reports' / 'eval_corpus.json'
if len(sys.argv) > 1:
    report = Path(sys.argv[1])

with open(report) as f:
    data = json.load(f)

# Build lookup: question text -> expected_collections from corpus YAML
_corpus_path = Path(__file__).parent.parent / 'configs' / 'eval_corpus.yaml'
_expected_cols: dict = {}
if _corpus_path.exists():
    _corpus = yaml.safe_load(_corpus_path.read_text())
    for q in _corpus.get('queries', []):
        _expected_cols[q['question']] = q.get('expected_collections') or []

def _get_expected_cols(r):
    # Report query may have "[Student context — ...]\n" prefix — strip it
    raw = r.get('query', '')
    question = raw.split('\n', 1)[-1] if raw.startswith('[Student context') else raw
    return _expected_cols.get(question, [])

total   = len(data)
passed  = [r for r in data if r.get('overall_success')]
failed  = [r for r in data if not r.get('overall_success')]

judged        = [r for r in data if r.get('judge_passed') is not None]
judge_passed  = [r for r in judged if r.get('judge_passed') is True]
judge_failed  = [r for r in judged if r.get('judge_passed') is False]
errored       = [r for r in data if 'error' in r]

tps_vals  = [r['judge_tokens_per_s'] for r in data if r.get('judge_tokens_per_s')]
time_vals = [r['elapsed_s'] for r in data if r.get('elapsed_s')]

def pct(n, d):
    return f"{100*n/d:.1f}%" if d else "n/a"

print(f"\n{'='*52}")
print(f"  Eval corpus summary  ({report.name})")
print(f"{'='*52}")
print(f"  Total questions      : {total}")
print(f"  Pass                 : {len(passed)} / {total}  ({pct(len(passed), total)})")
print(f"  Fail                 : {len(failed)} / {total}  ({pct(len(failed), total)})")
print(f"    of which errored   : {len(errored)}")
print(f"    of which judge fail: {len(judge_failed)}")
print(f"  Judge pass rate      : {len(judge_passed)} / {len(judged)}  ({pct(len(judge_passed), len(judged))})")

if time_vals:
    print(f"\n  Avg elapsed          : {sum(time_vals)/len(time_vals):.1f}s")
    print(f"  Min / Max elapsed    : {min(time_vals):.1f}s / {max(time_vals):.1f}s")

if tps_vals:
    print(f"\n  Avg judge tok/s      : {sum(tps_vals)/len(tps_vals):.1f}")
    print(f"  Min / Max tok/s      : {min(tps_vals):.1f} / {max(tps_vals):.1f}")

# Per-major / per-minor breakdown
by_major = defaultdict(lambda: {'pass': 0, 'fail': 0})
by_minor = defaultdict(lambda: {'pass': 0, 'fail': 0})
by_other = defaultdict(lambda: {'pass': 0, 'fail': 0})
for r in data:
    bucket = 'pass' if r.get('overall_success') else 'fail'
    if r.get('major'):
        by_major[r['major']][bucket] += 1
    elif r.get('minor'):
        by_minor[r['minor']][bucket] += 1
    else:
        expected = _get_expected_cols(r)
        if '4_year_plans' in expected:
            by_other['4_year_plans'][bucket] += 1
        else:
            by_other['general_knowledge'][bucket] += 1

def print_table(label, table):
    if not table:
        return
    print(f"\n  {label}")
    print(f"  {'Name':<30} {'Pass':>5} {'Fail':>5} {'Rate':>7}")
    print(f"  {'-'*30} {'-'*5} {'-'*5} {'-'*7}")
    for name in sorted(table):
        p, f = table[name]['pass'], table[name]['fail']
        print(f"  {name:<30} {p:>5} {f:>5} {pct(p, p+f):>7}")

print_table("By major:", by_major)
print_table("By minor:", by_minor)
print_table("General knowledge:", by_other)

print(f"{'='*52}\n")

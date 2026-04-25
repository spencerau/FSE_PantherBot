#!/usr/bin/env python3
"""
Build eval_corpus.yaml by sampling from sample_prompts/ JSON files.

Usage:
    PYTHONPATH=src python scripts/build_eval_corpus.py
    PYTHONPATH=src python scripts/build_eval_corpus.py --total 180 --seed 7
"""
import argparse
import json
import random
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent
PROMPTS_ROOT = PROJECT_ROOT / 'sample_prompts'

MAJOR_FILES = {
    'Computer Science':     PROMPTS_ROOT / 'major_catalogs/CompSci.json',
    'Data Science':         PROMPTS_ROOT / 'major_catalogs/DataSci.json',
    'Software Engineering': PROMPTS_ROOT / 'major_catalogs/SoftEng.json',
    'Computer Engineering': PROMPTS_ROOT / 'major_catalogs/CompE.json',
    'Electrical Engineering': PROMPTS_ROOT / 'major_catalogs/ElecEng.json',
}

MINOR_FILES = {
    'Game Development':            PROMPTS_ROOT / 'minor_catalogs/GameDev.json',
    'Analytics':                   PROMPTS_ROOT / 'minor_catalogs/Analytics.json',
    'Information Security Policy': PROMPTS_ROOT / 'minor_catalogs/ISP.json',
    'Computer Science':            PROMPTS_ROOT / 'minor_catalogs/CompSci.json',
    'Computer Engineering':        PROMPTS_ROOT / 'minor_catalogs/CompE.json',
    'Electrical Engineering':      PROMPTS_ROOT / 'minor_catalogs/ElecEng.json',
}

GENERAL_FILE = PROMPTS_ROOT / 'general_knowledge/general_info.json'

# Target proportions within each category
MAJOR_SPLITS = {
    'Computer Science':     0.35,
    'Data Science':         0.25,
    'Software Engineering': 0.20,
    'Computer Engineering': 0.10,
    'Electrical Engineering': 0.10,
}

MINOR_SPLITS = {
    'Game Development':            0.25,
    'Analytics':                   0.15,
    'Information Security Policy': 0.15,
    'Computer Science':            0.15,
    'Computer Engineering':        0.15,
    'Electrical Engineering':      0.15,
}

# Year weights for stratified sampling within catalog categories
YEAR_WEIGHTS = {2022: 0.10, 2023: 0.20, 2024: 0.35, 2025: 0.35}

CUSTOM_TEMPLATE = """\
  # ==================== CUSTOM (fill these in) ====================
  # Add 4-year plan queries, multi-collection, and harder questions here.
  # 30 entries recommended. Template:
  #
  # - year: "2025"
  #   major: "Computer Science"
  #   minor: "Game Development"     # optional — include for multi-collection
  #   question: "..."
  #   acceptable_answer: "Should mention: ..."
  #   sample_answer: "..."
  #   expected_collections: ["major_catalogs", "minor_catalogs"]
"""


def load_json(path: Path):
    with open(path) as f:
        return json.load(f)


def convert(item, major=None, minor=None, expected_collections=None):
    key_facts = item['answer'].get('key_facts', [])
    rubric = ('Should mention: ' + ', '.join(key_facts)) if key_facts else 'Should answer the question correctly.'
    entry = {'question': item['question']}
    year = item.get('year')
    if year:
        entry['year'] = str(year)
    if major:
        entry['major'] = major
    if minor:
        entry['minor'] = minor
    entry['acceptable_answer'] = rubric
    entry['sample_answer'] = item['answer']['canonical']
    if expected_collections:
        entry['expected_collections'] = expected_collections
    return entry


def stratified_sample(items, n, rng):
    """Sample n items stratified by year, falling back to random if needed."""
    if n <= 0:
        return []
    by_year = {}
    for item in items:
        y = item.get('year')
        by_year.setdefault(y, []).append(item)

    selected, used_ids = [], set()

    for year, weight in YEAR_WEIGHTS.items():
        target = max(1, round(n * weight))
        pool = [x for x in by_year.get(year, []) if id(x) not in used_ids]
        picked = rng.sample(pool, min(target, len(pool)))
        selected.extend(picked)
        used_ids.update(id(p) for p in picked)

    # Fill deficit from remaining items
    if len(selected) < n:
        remaining = [x for x in items if id(x) not in used_ids]
        extra = rng.sample(remaining, min(n - len(selected), len(remaining)))
        selected.extend(extra)

    rng.shuffle(selected)
    return selected[:n]


def build(total: int, seed: int):
    rng = random.Random(seed)
    # Proportions scaled to the 3 sampled categories only (major/minor/general).
    # 4-year plans and custom are added manually by the user.
    # Ratios: major 46%, minor 23%, general 31% (preserving original 30:15:20 ratio).
    n_major   = round(total * 0.46)
    n_minor   = round(total * 0.23)
    n_general = round(total * 0.31)

    entries = []

    # Majors
    for name, weight in MAJOR_SPLITS.items():
        n = max(1, round(n_major * weight))
        items = load_json(MAJOR_FILES[name])
        for item in stratified_sample(items, n, rng):
            entries.append(convert(item, major=name, expected_collections=['major_catalogs']))

    # Minors
    for name, weight in MINOR_SPLITS.items():
        n = max(1, round(n_minor * weight))
        items = load_json(MINOR_FILES[name])
        for item in stratified_sample(items, n, rng):
            entries.append(convert(item, minor=name, expected_collections=['minor_catalogs']))

    # General knowledge (no year/program)
    gen_items = load_json(GENERAL_FILE)
    for item in rng.sample(gen_items, min(n_general, len(gen_items))):
        entries.append(convert(item, expected_collections=['general_knowledge']))

    rng.shuffle(entries)
    return entries


def main():
    parser = argparse.ArgumentParser(description='Build eval_corpus.yaml from sample_prompts/')
    parser.add_argument('--total', type=int, default=120,
                        help='Target total questions (default: 120). Produces ~65%% as sampled '
                             '(major+minor+general); add 30 custom + 4-year plans to reach target.')
    parser.add_argument('--seed',  type=int, default=42, help='Random seed (default: 42)')
    parser.add_argument('--out',   default='configs/eval_corpus.yaml', help='Output file')
    args = parser.parse_args()

    entries = build(args.total, args.seed)
    out_path = PROJECT_ROOT / args.out

    header = (
        '# Eval corpus — auto-generated by scripts/build_eval_corpus.py\n'
        '# Review acceptable_answer rubrics before running the full eval.\n'
        '# Fill in the CUSTOM section at the bottom (4-year plans, multi-collection, harder questions).\n\n'
    )

    body = yaml.dump(
        {'queries': entries},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    with open(out_path, 'w') as f:
        f.write(header)
        f.write(body)
        f.write('\n')
        f.write(CUSTOM_TEMPLATE)

    print(f'Sampled {len(entries)} questions → {out_path}')
    print('Now fill in the CUSTOM section at the bottom with ~30 questions.')


if __name__ == '__main__':
    main()

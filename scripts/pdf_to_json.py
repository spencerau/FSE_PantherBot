#!/usr/bin/env python3
"""
Convert Chapman FSE major catalog PDFs to structured JSON using Docling + Ollama.

Docling handles the PDF → clean markdown conversion; Ollama does the structured
extraction.  The output schema matches data/major_catalog_json/.

Usage (from repo root):
    # Single file (output auto-derived)
    python scripts/pdf_to_json.py data/major_catalog/2025/2025_cs.pdf

    # Entire year directory
    python scripts/pdf_to_json.py data/major_catalog/2025/

    # Explicit output path
    python scripts/pdf_to_json.py data/major_catalog/2025/2025_cs.pdf \
        --output data/major_catalog_json/2025/2025_CompSci.json

    # Local Ollama (port 11434, gemma3:4b or similar)
    python scripts/pdf_to_json.py --local data/major_catalog/2025/2025_cs.pdf

    # Custom model / endpoint
    python scripts/pdf_to_json.py --host localhost --port 10001 \
        --model qwen3.5:35b data/major_catalog/2025/2025_cs.pdf
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Subject-code → metadata mapping
# Must stay in sync with configs/config.yaml domain.majors
# ---------------------------------------------------------------------------
SUBJECT_MAP: dict[str, dict] = {
    "cs": {"display": "Computer Science",     "filename": "CompSci", "degree": "B.S."},
    "ce": {"display": "Computer Engineering", "filename": "CompEng", "degree": "B.S."},
    "ds": {"display": "Data Science",         "filename": "DataSci", "degree": "B.S."},
    "ee": {"display": "Electrical Engineering","filename": "ElecEng","degree": "B.S."},
    "se": {"display": "Software Engineering", "filename": "SoftEng", "degree": "B.S."},
}

# ---------------------------------------------------------------------------
# Filename parsing helpers
# ---------------------------------------------------------------------------

def parse_pdf_stem(stem: str) -> tuple[str, str]:
    """
    Return (year, subject_code) from a filename stem like '2025_cs'.
    Raises ValueError if the stem doesn't match the expected pattern.
    """
    m = re.fullmatch(r"(\d{4})_([a-z]+)", stem.lower())
    if not m:
        raise ValueError(
            f"Cannot parse year/code from '{stem}'. "
            "Expected format: YYYY_<code>, e.g. 2025_cs"
        )
    year, code = m.group(1), m.group(2)
    if code not in SUBJECT_MAP:
        raise ValueError(
            f"Unknown subject code '{code}'. "
            f"Known codes: {', '.join(SUBJECT_MAP)}"
        )
    return year, code


def derive_output_path(pdf_path: Path) -> Path:
    """
    Map  data/major_catalog/<year>/<year>_<code>.pdf
    →    data/major_catalog_json/<year>/<year>_<filename>.json
    """
    year, code = parse_pdf_stem(pdf_path.stem)
    filename_stem = SUBJECT_MAP[code]["filename"]
    out_dir = pdf_path.parent.parent.parent / "major_catalog_json" / year
    return out_dir / f"{year}_{filename_stem}.json"


# ---------------------------------------------------------------------------
# Docling conversion
# ---------------------------------------------------------------------------

def pdf_to_markdown(pdf_path: str) -> str:
    try:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.pipeline_options import PdfPipelineOptions
    except ImportError:
        sys.exit(
            "docling is not installed.  Run: pip install docling"
        )

    pipeline_options = PdfPipelineOptions(do_ocr=False, do_table_structure=True)
    converter = DocumentConverter()
    print(f"  Converting PDF with Docling: {pdf_path}")
    result = converter.convert(str(pdf_path))
    md = result.document.export_to_markdown()
    print(f"  Docling: {len(md):,} chars of markdown")
    return md


# ---------------------------------------------------------------------------
# LLM extraction prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a structured data extraction assistant. "
    "Output ONLY valid JSON. No markdown code fences, no explanation."
)

_SCHEMA_DESCRIPTION = """\
Extract all information from the catalog text below into the following JSON schema.

SCHEMA (all string values unless type is shown):
{
  "program": "e.g. Computer Science, B.S.",
  "institution": "Chapman University",
  "academic_year": "e.g. 2025-2026",
  "requirements": {
    "GPA": { "lower_division": <number>, "major": <number> },
    "grade_requirement": "e.g. C- or higher",
    "upper_division_units": <number>
  },
  "sections": [ <see section schema below> ],
  "total_credits": "e.g. 77-78",
  "metadata": {
    "Year": "<catalog_year>",
    "DocumentType": "Major",
    "Subject": "<full subject name>",
    "SubjectCode": "<short code>"
  }
}

SECTION SCHEMA (one object per section heading in the catalog):
{
  "name": "Section heading, e.g. Grand Challenges Initiative",
  "credits": <number or "X-Y" string>,
  "notes": "Any introductory notes for this section (omit if none)",
  "courses": [ <COURSE objects, see below> ],

  // Lower-Division Core Requirements only: put the calculus/math choice sequences here
  "math_sequences": [
    { "notes": "optional", "sequence": 1, "courses": [ <COURSE objects> ] },
    { "sequence": 2, "courses": [ <COURSE objects> ] }
  ],

  // General Science Requirement only: put the lab-science choice sequences here
  "approved_sequences": [
    { "sequence": 1, "courses": [ <COURSE objects> ] },
    ...
  ]
}

COURSE SCHEMA:
{
  "course_number": "e.g. CPSC 350",
  "name": "Full course title",
  "prerequisite": "omit if none",
  "corequisite": "omit if none",
  "recommended_prerequisite": "omit if none",
  "credit_hours": <number>,
  "description": "Full description text including grading mode and offering frequency"
}

RULES:
1. Include EVERY course listed in the catalog for this program.
2. Lower-Division section: required courses go in "courses"; math choice sequences go in "math_sequences".
3. General Science Requirement section: all sequences go in "approved_sequences"; omit top-level "courses" key.
4. Colloquium: list the single repeatable colloquium course in "courses".
5. Electives: one flat "courses" list.
6. Professional Portfolio: one course in "courses".
7. Omit optional keys (prerequisite, corequisite, notes, etc.) when not present in the catalog.
8. academic_year: if catalog year is 2025, write "2025-2026"; 2024 → "2024-2025", etc.
9. credits field: use a number when exact, a string "X-Y" when a range is given.
10. Output valid JSON only — no comments, no trailing commas.
"""


def build_prompt(markdown: str, year: str, code: str) -> str:
    subject = SUBJECT_MAP[code]
    meta_hint = (
        f"\nThe program is '{subject['display']}, {subject['degree']}', "
        f"catalog year {year}.\n"
        f"Set metadata: Year=\"{year}\", Subject=\"{subject['display']}\", "
        f"SubjectCode=\"{code}\".\n\n"
    )
    return _SCHEMA_DESCRIPTION + meta_hint + "CATALOG TEXT:\n\n" + markdown


# ---------------------------------------------------------------------------
# Ollama call
# ---------------------------------------------------------------------------

def call_ollama(prompt: str, model: str, base_url: str, timeout: int = 600) -> str:
    import requests  # standard library request; no project dependency needed

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 32768,
            "num_ctx": 131072,
        },
        "think": False,  # suppress chain-of-thought tokens (qwen3 models)
    }

    print(f"  Calling {base_url}/api/chat  model={model}  (this may take a while)...")
    resp = requests.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def clean_llm_output(raw: str) -> str:
    """Strip thinking tags and markdown code fences from LLM output."""
    # Remove <think>…</think> blocks
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    # Strip ```json … ``` or ``` … ```
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


# ---------------------------------------------------------------------------
# Core processing
# ---------------------------------------------------------------------------

def process_pdf(
    pdf_path: Path,
    output_path: Path,
    model: str,
    base_url: str,
    timeout: int,
    overwrite: bool,
) -> bool:
    """Convert one PDF.  Returns True on success."""
    if output_path.exists() and not overwrite:
        print(f"  SKIP (already exists): {output_path}  — use --overwrite to regenerate")
        return True

    year, code = parse_pdf_stem(pdf_path.stem)

    # 1. Docling → markdown
    markdown = pdf_to_markdown(str(pdf_path))

    # 2. Build prompt
    prompt = build_prompt(markdown, year, code)
    print(f"  Prompt length: {len(prompt):,} chars")

    # 3. LLM extraction
    raw = call_ollama(prompt, model, base_url, timeout)
    cleaned = clean_llm_output(raw)

    # 4. Parse JSON
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        # Attempt to salvage: find the outermost { … }
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group())
            except json.JSONDecodeError:
                print(f"  ERROR: Could not parse LLM output as JSON: {exc}")
                bad_path = output_path.with_suffix(".bad.txt")
                bad_path.write_text(cleaned)
                print(f"  Raw LLM output saved to: {bad_path}")
                return False
        else:
            print(f"  ERROR: Could not parse LLM output as JSON: {exc}")
            bad_path = output_path.with_suffix(".bad.txt")
            bad_path.write_text(cleaned)
            print(f"  Raw LLM output saved to: {bad_path}")
            return False

    # 5. Ensure metadata is present and correct
    data.setdefault("metadata", {})
    data["metadata"].update({
        "Year": year,
        "DocumentType": "Major",
        "Subject": SUBJECT_MAP[code]["display"],
        "SubjectCode": code,
    })

    # 6. Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"  Wrote: {output_path}")
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert FSE major catalog PDFs to structured JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "input",
        help="Path to a PDF file or a directory of PDFs.",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output JSON path (single-file mode only; auto-derived if omitted).",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Ollama model name (default: qwen3.5:35b, or qwen3:4b with --local).",
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Ollama host (default: localhost).",
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=None,
        help="Ollama port (default: 10001 cluster, 11434 local).",
    )
    parser.add_argument(
        "--local", "-l",
        action="store_true",
        help="Use local Ollama on port 11434 with a smaller model.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Request timeout in seconds (default: 600).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files.",
    )
    args = parser.parse_args()

    # Resolve Ollama endpoint
    host = args.host or "localhost"
    if args.local:
        port  = args.port  or 11434
        model = args.model or "qwen3:4b"
    else:
        port  = args.port  or 10001
        model = args.model or "qwen3.5:35b"

    base_url = f"http://{host}:{port}"
    print(f"Ollama endpoint: {base_url}  model: {model}")

    # Collect PDFs to process
    input_path = Path(args.input)
    if input_path.is_dir():
        pdfs = sorted(input_path.glob("*.pdf"))
        if not pdfs:
            sys.exit(f"No PDF files found in: {input_path}")
        if args.output:
            sys.exit("--output cannot be used with a directory input.")
        pairs = [(p, derive_output_path(p)) for p in pdfs]
    elif input_path.is_file():
        out = Path(args.output) if args.output else derive_output_path(input_path)
        pairs = [(input_path, out)]
    else:
        sys.exit(f"Input path not found: {input_path}")

    # Process
    ok = failed = 0
    for pdf_path, out_path in pairs:
        print(f"\n[{pdf_path.name}]")
        try:
            success = process_pdf(
                pdf_path, out_path, model, base_url, args.timeout, args.overwrite
            )
        except Exception as exc:
            print(f"  ERROR: {exc}")
            success = False

        if success:
            ok += 1
        else:
            failed += 1

    print(f"\nDone: {ok} succeeded, {failed} failed.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

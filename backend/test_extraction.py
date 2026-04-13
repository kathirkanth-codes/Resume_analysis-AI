# =============================================================================
# test_extraction.py
# =============================================================================
# PURPOSE  : Quick CLI test for Steps 1 + 2 of the pipeline.
#            Asks for a PDF path, runs the parser, runs extraction, prints results.
# USAGE    : python test_extraction.py
# =============================================================================

import json
import sys
import os

# Allow running from any directory by adding project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_parser import parse_resume
from resume_extraction import extract_resume


def _print_section(title: str, content):
    width = 60
    print(f"\n{'=' * width}")
    print(f"  {title}")
    print(f"{'=' * width}")
    if isinstance(content, list):
        if not content:
            print("  (none found)")
        for i, item in enumerate(content, 1):
            if isinstance(item, dict):
                print(f"\n  [{i}]")
                for k, v in item.items():
                    val = v if v else "(not detected)"
                    # Wrap long values
                    if len(str(val)) > 80:
                        val = str(val)[:77] + "..."
                    print(f"    {k:15s}: {val}")
            else:
                print(f"  - {item}")
    else:
        print(content if content else "  (none found)")


def save_json(data: dict):
    """
    Asks for a filename, sanitizes it, and writes data as a formatted JSON file.
    Shared utility — also imported by test_evaluator.py.
    """
    name = input("  Enter filename (without .json) [default: resume_output]: ").strip()
    if not name:
        name = "resume_output"
    name = name.replace(" ", "_")
    filepath = f"{name}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  [Saved] → {filepath}")


def main():
    print("\n" + "=" * 60)
    print("  AI Resume Analyzer — Extraction Test")
    print("=" * 60)

    pdf_path = input("\nEnter path to resume PDF: ").strip().strip('"').strip("'")

    if not os.path.isfile(pdf_path):
        print(f"\n[ERROR] File not found: {pdf_path}")
        sys.exit(1)

    # ── Step 1: Parse PDF ─────────────────────────────────────
    print("\n[Step 1] Parsing PDF...")
    sections = parse_resume(pdf_path)

    if not sections:
        print("[ERROR] Parser returned empty result. Check the PDF.")
        sys.exit(1)

    print(f"  Sections detected: {list(sections.keys())}")

    # ── Step 2: Extract structured data ───────────────────────
    print("\n[Step 2] Extracting structured data...")
    structured = extract_resume(sections)

    # ── Display results ────────────────────────────────────────
    _print_section("SKILLS", structured["skills"])
    _print_section("EXPERIENCE", structured["experience"])
    _print_section("EDUCATION", structured["education"])
    _print_section("PROJECTS", structured["projects"])

    # ── Stats summary ──────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  SUMMARY STATS")
    print(f"{'=' * 60}")
    print(f"  Skills found     : {len(structured['skills'])}")
    print(f"  Experience items : {len(structured['experience'])}")
    print(f"  Education items  : {len(structured['education'])}")
    print(f"  Projects found   : {len(structured['projects'])}")
    print()

    # ── Optional: save as JSON file ───────────────────────────
    save = input("Save output as JSON file? (y/n): ").strip().lower()
    if save == 'y':
        save_json(structured)


if __name__ == "__main__":
    main()
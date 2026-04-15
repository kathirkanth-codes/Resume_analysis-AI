# =============================================================================
# test_parser.py
# =============================================================================
# PURPOSE  : Quick CLI test for Step 1 ONLY (pdf_parser).
#            Shows the raw section text BEFORE resume_extraction touches it.
#            Use this to debug word concatenation, missing sections, or
#            wrong text landing in the wrong section.
# USAGE    : python test_parser.py
# =============================================================================

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_parser import parse_resume


# ─────────────────────────────────────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

WIDTH = 60


def _print_raw_section(section_name: str, raw_text: str):
    """Print raw section text with line numbers so problems are easy to spot."""
    print(f"\n{'=' * WIDTH}")
    print(f"  SECTION: {section_name}")
    print(f"{'=' * WIDTH}")

    if not raw_text.strip():
        print("  (empty)")
        return

    lines = raw_text.split('\n')
    print(f"  Lines in section: {len(lines)}\n")
    for i, line in enumerate(lines, 1):
        # Flag concatenated words (no spaces, long token) so they stand out
        flag = " ◄ CONCATENATED?" if _looks_concatenated(line) else ""
        print(f"  {i:>3}  {line}{flag}")


def _looks_concatenated(line: str) -> bool:
    """
    Heuristic: if the longest word in a line is > 25 chars and has no spaces
    inside it, it is likely a concatenation artifact from the PDF parser.
    """
    words = line.strip().split()
    if not words:
        return False
    longest = max(len(w) for w in words)
    return longest > 25


def _print_stats(sections: dict):
    """Print a quick summary of what was detected."""
    print(f"\n{'=' * WIDTH}")
    print("  PARSER STATS")
    print(f"{'=' * WIDTH}")
    print(f"  Sections detected : {list(sections.keys())}")
    for name, text in sections.items():
        line_count = len([l for l in text.split('\n') if l.strip()])
        word_count = len(text.split())
        print(f"  {name:<22}: {line_count} lines, {word_count} words")


def _check_health(sections: dict):
    """
    Print a simple health report — warns about common parser problems.
    This is the first thing to read when debugging.
    """
    print(f"\n{'=' * WIDTH}")
    print("  HEALTH CHECK")
    print(f"{'=' * WIDTH}")

    expected = ["SKILLS", "EXPERIENCE", "EDUCATION", "PROJECTS"]
    issues_found = False

    # Check: expected sections present
    for key in expected:
        if key not in sections:
            print(f"  [MISSING]  '{key}' section not detected.")
            issues_found = True

    # Check: concatenated words in each section
    for name, text in sections.items():
        bad_lines = []
        for i, line in enumerate(text.split('\n'), 1):
            if _looks_concatenated(line):
                bad_lines.append(i)
        if bad_lines:
            print(f"  [CONCAT]   '{name}' has concatenated words on lines: {bad_lines}")
            issues_found = True

    # Check: skills section empty or suspiciously short
    skills_text = sections.get("SKILLS", "")
    if len(skills_text.strip()) < 20:
        print(f"  [WARNING]  SKILLS section is very short or empty — may be misparsed.")
        issues_found = True

    if not issues_found:
        print("  All checks passed. No obvious problems detected.")


# ─────────────────────────────────────────────────────────────────────────────
# SAVE HELPERS  (same pattern as test_extraction.py)
# ─────────────────────────────────────────────────────────────────────────────

def save_json(data: dict):
    name = input("  Enter filename (without .json) [default: parser_output]: ").strip()
    if not name:
        name = "parser_output"
    name = name.replace(" ", "_")
    filepath = f"{name}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  [Saved] → {filepath}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "=" * WIDTH)
    print("  AI Resume Analyzer — Parser Test (Step 1 only)")
    print("=" * WIDTH)

    pdf_path = input("\nEnter path to resume PDF: ").strip().strip('"').strip("'")

    if not os.path.isfile(pdf_path):
        print(f"\n[ERROR] File not found: {pdf_path}")
        sys.exit(1)

    # ── Run parser ────────────────────────────────────────────────
    print("\n[Step 1] Running pdf_parser...")
    sections = parse_resume(pdf_path)

    if not sections:
        print("[ERROR] Parser returned empty result. PDF may be image-based.")
        sys.exit(1)

    # ── Health check first — read this before the raw output ──────
    _check_health(sections)

    # ── Raw section output ─────────────────────────────────────────
    print(f"\n{'=' * WIDTH}")
    print("  RAW SECTION TEXT  (what resume_extraction will receive)")
    print(f"{'=' * WIDTH}")

    for section_name, raw_text in sections.items():
        _print_raw_section(section_name, raw_text)

    # ── Stats ──────────────────────────────────────────────────────
    _print_stats(sections)

    # ── Save option ────────────────────────────────────────────────
    print()
    save = input("Save raw sections as JSON file? (y/n): ").strip().lower()
    if save == 'y':
        save_json(sections)


if __name__ == "__main__":
    main()
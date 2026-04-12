# =============================================================================
# test_parser.py
# =============================================================================
# PURPOSE  : Test pdf_parser.py interactively.
# =============================================================================

import json
import os
import sys
from datetime import datetime

from pdf_parser import parse_resume


# ─────────────────────────────────────────────────────────────────────────────
# DISPLAY
# ─────────────────────────────────────────────────────────────────────────────

def banner(title: str):
    width = 65
    print("\n" + "=" * width)
    print(f"  {title}")
    print("=" * width)


def print_section(name: str, content: str):
    print(f"\n  ┌── {name} {'─' * (55 - len(name))}")
    lines = content.split('\n')
    for line in lines:
        print(f"  │  {line}")
    print(f"  └{'─' * 60}")


def print_stats(sections: dict):
    banner("STATS — Quick quality check")
    print(f"  {'Section':<26} {'Lines':>5}  {'Chars':>6}")
    print(f"  {'─' * 26} {'─' * 5}  {'─' * 6}")
    total = 0
    for name, content in sections.items():
        n_lines = content.count('\n') + 1 if content else 0
        n_chars = len(content)
        total += n_chars
        print(f"  {name:<26} {n_lines:>5}  {n_chars:>6}")
    print(f"  {'─' * 40}")
    print(f"  {'TOTAL':<26} {'':>5}  {total:>6} chars")


# ─────────────────────────────────────────────────────────────────────────────
# INPUT
# ─────────────────────────────────────────────────────────────────────────────

def ask_pdf_path() -> str:
    print("\n  Enter the full path to your resume PDF.\n")

    while True:
        path = input("  PDF path: ").strip().strip('"').strip("'")

        if not path:
            print("  [!] Path cannot be empty.\n")
            continue

        if not os.path.isfile(path):
            print(f"  [!] File not found: {path}\n")
            continue

        return path


def ask_output_name() -> str:
    print("\n  Enter output JSON filename (no extension needed)\n")

    while True:
        name = input("  Output filename: ").strip()

        if not name:
            print("  [!] Name cannot be empty.\n")
            continue

        if name.lower().endswith('.json'):
            name = name[:-5]

        safe = "".join(c for c in name if c.isalnum() or c in ('_', '-', ' '))
        safe = safe.strip().replace(' ', '_')

        if not safe:
            print("  [!] Invalid name.\n")
            continue

        return safe + '.json'


# ─────────────────────────────────────────────────────────────────────────────
# JSON SAVE
# ─────────────────────────────────────────────────────────────────────────────

def save_json(sections: dict, pdf_path: str, filename: str) -> str:
    output = {
        "metadata": {
            "source_file": os.path.basename(pdf_path),
            "parsed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "sections_found": len(sections),
            "section_names": list(sections.keys()),
        },
        "sections": sections
    }

    save_dir = os.path.dirname(os.path.abspath(__file__))
    save_path = os.path.join(save_dir, filename)

    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return save_path


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    banner("test_parser.py — Resume Parser Tester")

    # Step 1: Inputs
    banner("STEP 1 — Inputs")
    pdf_path = ask_pdf_path()
    output_name = ask_output_name()

    # Step 2: Run parser
    banner("STEP 2 — Running Parser")

    DEBUG = True  # ← change to False when not debugging

    if DEBUG:
        from pdf_parser import extract_raw_text, clean_text

        print("\n===== DEBUG: RAW TEXT =====\n")
        raw = extract_raw_text(pdf_path)
        print(raw[:2000])

        print("\n===== DEBUG: CLEANED TEXT =====\n")
        cleaned = clean_text(raw)
        print(cleaned[:2000])

        print("\n===== DEBUG: FINAL SECTIONS =====\n")
        sections = parse_resume(pdf_path)

    else:
        sections = parse_resume(pdf_path)

    # Step 3: Validate
    if not sections:
        print("\n[ERROR] No sections extracted.")
        sys.exit(1)

    # Step 4: Display
    banner("STEP 3 — Extracted Sections")
    for name, content in sections.items():
        print_section(name, content)

    # Step 5: Stats
    print_stats(sections)

    # Step 6: Save JSON
    banner("STEP 4 — Saving JSON")
    path = save_json(sections, pdf_path, output_name)
    print(f"  Saved → {path}")

    banner("DONE")


if __name__ == "__main__":
    main()
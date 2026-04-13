# =============================================================================
# test_evaluator.py
# =============================================================================
# PURPOSE  : Quick CLI test for Steps 1 + 2 + 3 of the pipeline.
#            Asks for a PDF path, runs parser → extraction → evaluation.
#            Optionally accepts a job description for gap analysis.
# USAGE    : python test_evaluator.py
# =============================================================================

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pdf_parser       import parse_resume
from resume_extraction import extract_resume
from ai_evaluator     import evaluate_resume


WIDTH = 60


# =============================================================================
# DISPLAY HELPERS
# =============================================================================

def _print_section(title: str, content):
    print(f"\n{'=' * WIDTH}")
    print(f"  {title}")
    print(f"{'=' * WIDTH}")
    if isinstance(content, list):
        if not content:
            print("  (none found)")
        for i, item in enumerate(content, 1):
            if isinstance(item, dict):
                print(f"\n  [{i}]")
                for k, v in item.items():
                    val = v if v else "(not detected)"
                    if len(str(val)) > 80:
                        val = str(val)[:77] + "..."
                    print(f"    {k:15s}: {val}")
            else:
                print(f"  - {item}")
    else:
        print(content if content else "  (none found)")


def _print_score(result: dict):
    """Print the final score and section breakdown clearly."""
    score = result.get("score", 0)
    section_scores = result.get("section_scores", {})

    print(f"\n{'=' * WIDTH}")
    print(f"  FINAL SCORE: {score} / 100")
    print(f"{'=' * WIDTH}")

    maxes = {
        "bullet_strength": 30,
        "skill_coverage":  25,
        "project_impact":  25,
        "education":       10,
        "completeness":    10,
    }
    for key, cap in maxes.items():
        val = section_scores.get(key, 0)
        bar = "█" * val + "░" * (cap - val)
        print(f"  {key:<18}: {val:>2}/{cap}  {bar}")


def _print_reasoning(result: dict):
    print(f"\n{'=' * WIDTH}")
    print("  RECRUITER OBSERVATIONS")
    print(f"{'=' * WIDTH}")
    for obs in result.get("reasoning", []):
        print(f"  • {obs}")


def _print_weak_points(result: dict):
    weak = result.get("weak_points", [])
    print(f"\n{'=' * WIDTH}")
    print("  WEAK BULLETS + REWRITES")
    print(f"{'=' * WIDTH}")
    if not weak:
        print("  No weak bullets detected.")
        return
    for i, wp in enumerate(weak, 1):
        print(f"\n  [{i}] ORIGINAL:")
        print(f"      {wp.get('original', '')}")
        print(f"  [{i}] IMPROVED:")
        print(f"      {wp.get('improved', '')}")


def _print_missing_skills(result: dict):
    missing = result.get("missing_skills", [])
    print(f"\n{'=' * WIDTH}")
    print("  MISSING SKILLS")
    print(f"{'=' * WIDTH}")
    if not missing:
        print("  None detected.")
        return
    for skill in missing:
        print(f"  • {skill}")


def save_json(data: dict):
    """Save output as a JSON file. Same pattern as test_extraction.py."""
    name = input("  Enter filename (without .json) [default: eval_output]: ").strip()
    if not name:
        name = "eval_output"
    name = name.replace(" ", "_")
    filepath = f"{name}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  [Saved] → {filepath}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "=" * WIDTH)
    print("  AI Resume Analyzer — Full Pipeline Test (Steps 1 + 2 + 3)")
    print("=" * WIDTH)

    # ── Input: PDF path ───────────────────────────────────────────
    pdf_path = input("\nEnter path to resume PDF: ").strip().strip('"').strip("'")

    if not os.path.isfile(pdf_path):
        print(f"\n[ERROR] File not found: {pdf_path}")
        sys.exit(1)

    # ── Input: Optional job description ──────────────────────────
    print("\nEnter job description for gap analysis.")
    print("(Press Enter to skip — evaluator will suggest common skills instead)")
    jd = input("Job Description: ").strip()
    job_description = jd if jd else None

    # ── Step 1: Parse PDF ─────────────────────────────────────────
    print(f"\n{'─' * WIDTH}")
    print("[Step 1] Parsing PDF...")
    sections = parse_resume(pdf_path)

    if not sections:
        print("[ERROR] Parser returned empty result. Check the PDF.")
        sys.exit(1)

    print(f"  Sections detected: {list(sections.keys())}")

    # ── Step 2: Extract structured data ──────────────────────────
    print(f"\n{'─' * WIDTH}")
    print("[Step 2] Extracting structured data...")
    structured = extract_resume(sections)

    print(f"  Skills found     : {len(structured['skills'])}")
    print(f"  Experience items : {len(structured['experience'])}")
    print(f"  Education items  : {len(structured['education'])}")
    print(f"  Projects found   : {len(structured['projects'])}")

    # ── Step 3: AI Evaluation ─────────────────────────────────────
    print(f"\n{'─' * WIDTH}")
    print("[Step 3] Running AI evaluation (Gemini 1.5 Flash)...")
    result = evaluate_resume(structured, job_description=job_description)

    # ── Display results ───────────────────────────────────────────
    _print_score(result)
    _print_reasoning(result)
    _print_weak_points(result)
    _print_missing_skills(result)

    # ── Combined output for saving ────────────────────────────────
    full_output = {
        "resume_path":  pdf_path,
        "extraction":   structured,
        "evaluation":   result,
    }

    print(f"\n{'=' * WIDTH}")
    print()
    save = input("Save full output as JSON file? (y/n): ").strip().lower()
    if save == 'y':
        save_json(full_output)


if __name__ == "__main__":
    main()
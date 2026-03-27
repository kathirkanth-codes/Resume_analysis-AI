"""
test_pdf_parser.py — Comprehensive tester for pdf_parser v2

Tests all v2 features:
  - Basic info & metadata
  - Full text preview
  - Page-wise summary (with column detection)
  - Section detection & chunks
  - Warnings report
  - NLP readiness check
  - Export to .txt
"""

from pdf_parser import parse_pdf
import os
import json


# ── HELPERS ─────────────────────────────────────────────

def divider(title=""):
    width = 60
    if title:
        pad = (width - len(title) - 2) // 2
        print("\n" + "─" * pad + f" {title} " + "─" * pad)
    else:
        print("\n" + "─" * width)


def truncate(text, limit=400):
    return text[:limit] + f"\n... [{len(text) - limit} more chars]" if len(text) > limit else text


def warn_icon(reason):
    icons = {
        "scanned_detected":    "🔍",
        "garbage_text":        "🗑️",
        "extraction_failed":   "❌",
        "sparse_content":      "📄",
        "no_sections_detected":"⚠️",
    }
    return icons.get(reason, "⚠️")


# ── SECTIONS ────────────────────────────────────────────

def print_basic_info(result):
    divider("BASIC INFO")
    print(f"  File        : {result['file_path']}")
    print(f"  Pages       : {result['total_pages']}")
    print(f"  Scanned     : {'Yes ⚠️' if result['is_scanned'] else 'No ✅'}")

    failed = [p["page_number"] for p in result["pages"] if p["extraction_failed"]]
    print(f"  Failed Pages: {failed if failed else 'None ✅'}")

    if result["metadata"]:
        print(f"\n  Metadata:")
        for k, v in result["metadata"].items():
            print(f"    {k}: {v}")


def print_page_summary(result):
    divider("PAGE SUMMARY")
    print(f"  {'Page':<6} {'Chars':<8} {'Columns':<10} {'Failed':<8} {'Status'}")
    print(f"  {'─'*4:<6} {'─'*5:<8} {'─'*7:<10} {'─'*6:<8} {'─'*10}")

    for page in result["pages"]:
        chars = len(page["text"])
        cols  = page.get("num_columns", 1)
        fail  = page["extraction_failed"]

        if fail:
            status = "❌ Failed"
        elif chars == 0:
            status = "⚠️  Empty"
        elif chars < 50:
            status = "⚠️  Sparse"
        elif cols > 1:
            status = f"✅ OK ({cols}-col)"
        else:
            status = "✅ OK"

        print(f"  {page['page_number']:<6} {chars:<8} {cols:<10} {str(fail):<8} {status}")


def print_text_preview(result):
    divider("FULL TEXT PREVIEW (first 600 chars)")
    preview = result["full_text"][:600]
    print(preview)
    remaining = len(result["full_text"]) - 600
    if remaining > 0:
        print(f"\n  ... [{remaining} more chars in full_text]")


def print_sections(result):
    divider("DETECTED SECTIONS")

    sections = result.get("sections", [])
    if not sections:
        print("  ⚠️  No sections detected.")
        print("  Possible reasons:")
        print("    - Section headers are image-based (not selectable text)")
        print("    - Headers use unusual casing or abbreviations")
        print("    - Font-mapping issue caused headers to become garbage")
        return

    print(f"  Found {len(sections)} section(s):\n")
    for s in sections:
        print(f"  [{s['name']}]")
        print(f"    Line {s['line_number']} | Offset {s['char_offset']} chars")

    chunks = result.get("section_chunks", {})
    if chunks:
        divider("SECTION CHUNKS (preview)")
        for name, content in chunks.items():
            print(f"\n  ── {name} ──")
            print(f"  {truncate(content, 250)}")


def print_warnings(result):
    warnings = result.get("warnings", [])
    divider("WARNINGS")

    if not warnings:
        print("  ✅ No warnings — clean extraction")
        return

    print(f"  {len(warning for warning in warnings)} issue(s) found:\n")
    for w in warnings:
        icon = warn_icon(w["reason"])
        print(f"  {icon}  Page {w['page']} | {w['reason']}")
        print(f"      {w['detail']}")


def print_nlp_readiness(result):
    divider("NLP READINESS CHECK")

    full_text   = result.get("full_text", "")
    sections    = result.get("sections", [])
    warnings    = result.get("warnings", [])
    is_scanned  = result.get("is_scanned", False)
    total_pages = result.get("total_pages", 1)

    checks = []

    # 1. Minimum text volume
    chars = len(full_text.strip())
    checks.append((
        chars > 200,
        f"Text volume: {chars} chars",
        "Very little text extracted — check for scanned/image PDF"
    ))

    # 2. Section detection
    checks.append((
        len(sections) >= 2,
        f"Sections detected: {len(sections)}",
        "Fewer than 2 sections found — NLP chunking will be unreliable"
    ))

    # 3. No scanned flag
    checks.append((
        not is_scanned,
        "Not a scanned PDF",
        "Scanned PDF — OCR recommended before NLP (Tesseract / AWS Textract)"
    ))

    # 4. No failed pages
    failed_pages = [p for p in result["pages"] if p["extraction_failed"]]
    checks.append((
        len(failed_pages) == 0,
        f"Failed pages: {len(failed_pages)}",
        f"{len(failed_pages)} page(s) failed extraction — data loss likely"
    ))

    # 5. No extraction_failed warnings
    hard_failures = [w for w in warnings if w["reason"] == "extraction_failed"]
    checks.append((
        len(hard_failures) == 0,
        "No hard extraction failures",
        f"{len(hard_failures)} page(s) returned empty from both extractors"
    ))

    # 6. Structure preserved (double newlines present = sections likely intact)
    has_structure = "\n\n" in full_text
    checks.append((
        has_structure,
        "Paragraph/section breaks preserved in text",
        "No double-newlines found — text may be fully flattened (check clean_text)"
    ))

    passed = sum(1 for ok, _, _ in checks if ok)
    total  = len(checks)

    print(f"  Score: {passed}/{total}\n")
    for ok, label, fix in checks:
        icon = "✅" if ok else "❌"
        print(f"  {icon}  {label}")
        if not ok:
            print(f"       → {fix}")

    print()
    if passed == total:
        print("  ✅ Text is ready for keyword extraction, embeddings, and similarity scoring.")
    elif passed >= total - 2:
        print("  ⚠️  Minor issues — usable but review warnings before NLP pipeline.")
    else:
        print("  ❌ Significant issues — fix extraction before downstream NLP.")


def export_result(result, pdf_path):
    divider("EXPORT")

    base = os.path.splitext(pdf_path)[0]

    # Export full text
    txt_path = base + "_extracted.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(result["full_text"])
    print(f"  📄 Full text   → {txt_path}")

    # Export section chunks as JSON
    if result.get("section_chunks"):
        json_path = base + "_sections.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result["section_chunks"], f, indent=2, ensure_ascii=False)
        print(f"  📋 Sections    → {json_path}")

    # Export warnings as JSON
    if result.get("warnings"):
        warn_path = base + "_warnings.json"
        with open(warn_path, "w", encoding="utf-8") as f:
            json.dump(result["warnings"], f, indent=2, ensure_ascii=False)
        print(f"  ⚠️  Warnings    → {warn_path}")


# ── MAIN ────────────────────────────────────────────────

def main():
    print("\n╔══════════════════════════════════════════╗")
    print("║       PDF Parser v2 — Test Suite         ║")
    print("╚══════════════════════════════════════════╝")

    # ── Input ──
    pdf_path = input("\nEnter path to resume PDF: ").strip().strip('"').strip("'")

    if not os.path.exists(pdf_path):
        print("\n❌ File not found. Check the path and try again.")
        return

    if not pdf_path.lower().endswith(".pdf"):
        print("\n❌ Not a PDF file.")
        return

    print("\n⏳ Parsing...\n")

    try:
        result = parse_pdf(pdf_path)
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        return
    except ValueError as e:
        print(f"\n❌ {e}")
        return
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return

    # ── Run all test sections ──
    print_basic_info(result)
    print_page_summary(result)
    print_text_preview(result)
    print_sections(result)
    print_warnings(result)
    print_nlp_readiness(result)

    # ── Optional export ──
    divider()
    export_choice = input("\nExport results to files? (y/n): ").strip().lower()
    if export_choice == "y":
        export_result(result, pdf_path)

    divider()
    print("\n✅ Test complete.\n")


if __name__ == "__main__":
    main()
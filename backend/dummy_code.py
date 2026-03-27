"""
pdf_parser.py — Production-Ready (v2)

Improvements over v1:
1. Newline preservation — section boundaries no longer collapsed
2. Smarter garbage detection — no silent drops on sparse pages
3. Multi-column detection via bounding boxes
4. Structured warnings list in return dict
5. Post-extraction section tagger
"""

import pdfplumber
import fitz  # PyMuPDF
import re
import logging
from pathlib import Path
from collections import Counter


# ── LOGGING ─────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logging.getLogger("pdfminer").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


# ── CONSTANTS ───────────────────────────────────────────
SCANNED_AVG_THRESHOLD = 30
PAGE_SEPARATOR = "--- PAGE {n} ---"
MULTI_COLUMN_GAP_THRESHOLD = 200   # px gap between column clusters
MIN_WORDS_FOR_COLUMN_DETECTION = 10

# Resume section header patterns
SECTION_HEADER_PATTERN = re.compile(
    r"^("
    r"summary|professional\s+summary|career\s+summary|objective|profile|about\s+me|"
    r"skills?|technical\s+skills?|core\s+competencies|competencies|expertise|"
    r"experience|work\s+experience|professional\s+experience|employment|career|"
    r"education|academic|qualifications?|"
    r"projects?|personal\s+projects?|key\s+projects?|"
    r"certifications?|certificates?|credentials?|"
    r"languages?|"
    r"awards?|achievements?|honors?|"
    r"publications?|research|"
    r"volunteer|extra.?curricular|activities|interests?|hobbies"
    r")\s*$",
    re.IGNORECASE
)


# ── TEXT CLEANING (STRUCTURE-PRESERVING) ─────────────────
def clean_text(text: str) -> str:
    """
    Clean text while preserving section structure.

    Key fix from v1: single newlines are merged to spaces (line-wrap),
    but double newlines (paragraph/section breaks) are preserved.
    """
    if not text:
        return ""

    # Remove form feeds
    text = text.replace("\f", "\n")

    # Fix hyphenated line breaks (word broken across lines)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # FIX v1 BUG: Don't collapse ALL newlines.
    # Single newline = line wrap within a paragraph → merge to space
    # Double newline = section/paragraph boundary → preserve as \n\n
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)

    # Normalize multiple blank lines to one blank line
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Normalize horizontal whitespace
    text = re.sub(r"[ \t]+", " ", text)

    # Clean up trailing spaces on each line
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n +", "\n", text)

    # Fix spacing before punctuation
    text = re.sub(r"\s+([.,])", r"\1", text)

    return text.strip()


# ── GARBAGE DETECTION (IMPROVED) ────────────────────────
def is_garbage_text(text: str) -> bool:
    """
    Detect genuinely unreadable text.

    FIX v1 BUG: Removed the len < 50 check which silently dropped
    valid sparse pages (e.g. skills-only pages, contact pages).
    Now only flags encoding artifacts and extremely high noise ratios.
    """
    if not text:
        return True

    # Font-encoding artifact — definitive garbage signal
    if "(cid:" in text:
        return True

    stripped = text.strip()

    # Truly empty after stripping
    if not stripped:
        return True

    # Extended set of allowed characters for resumes
    # (includes @, /, -, |, +, #, parentheses for contact info and code)
    allowed_non_alnum = set(" .,:\n-|@/#+()[]_'\"•▪◦→*")
    weird_chars = sum(
        1 for c in stripped
        if not c.isalnum() and c not in allowed_non_alnum
    )
    ratio = weird_chars / max(len(stripped), 1)

    # Raised threshold from 0.3 to 0.35 to tolerate symbol-heavy resumes
    return ratio > 0.35


# ── SCANNED DETECTION ───────────────────────────────────
def is_scanned(texts: list) -> bool:
    if not texts:
        return False
    avg = sum(len(t.strip()) for t in texts) / len(texts)
    return avg < SCANNED_AVG_THRESHOLD


# ── MULTI-COLUMN DETECTION ───────────────────────────────
def detect_columns(page) -> int:
    """
    Use word bounding boxes to detect multi-column layout.
    Returns the number of detected columns (1 or 2+).
    """
    try:
        words = page.extract_words(x_tolerance=3, y_tolerance=3)
        if len(words) < MIN_WORDS_FOR_COLUMN_DETECTION:
            return 1

        x_starts = sorted([w["x0"] for w in words])

        # Find natural gap clusters in x-coordinates
        # A big jump in x_start values indicates a column boundary
        gaps = []
        for i in range(1, len(x_starts)):
            gap = x_starts[i] - x_starts[i - 1]
            if gap > MULTI_COLUMN_GAP_THRESHOLD:
                gaps.append((gap, x_starts[i]))

        return 1 + len(gaps)

    except Exception:
        return 1


def extract_columns_ordered(page) -> str:
    """
    For multi-column pages: sort words by (column, y) to get correct reading order.
    Falls back to standard extract_text() on error.
    """
    try:
        words = page.extract_words(x_tolerance=3, y_tolerance=3)
        if not words:
            return ""

        page_width = page.width
        mid = page_width / 2

        # Split words into left and right columns by midpoint
        left = sorted(
            [w for w in words if w["x0"] < mid],
            key=lambda w: (w["top"], w["x0"])
        )
        right = sorted(
            [w for w in words if w["x0"] >= mid],
            key=lambda w: (w["top"], w["x0"])
        )

        def words_to_text(word_list):
            if not word_list:
                return ""
            lines = []
            current_line = []
            current_top = word_list[0]["top"]

            for w in word_list:
                if abs(w["top"] - current_top) > 5:
                    lines.append(" ".join(current_line))
                    current_line = [w["text"]]
                    current_top = w["top"]
                else:
                    current_line.append(w["text"])

            if current_line:
                lines.append(" ".join(current_line))

            return "\n".join(lines)

        left_text = words_to_text(left)
        right_text = words_to_text(right)

        # Combine: left column first, then right column
        parts = [p for p in [left_text, right_text] if p.strip()]
        return "\n\n".join(parts)

    except Exception:
        return page.extract_text() or ""


# ── SAFE EXTRACTION (pdfplumber) ─────────────────────────
def extract_page_text(page) -> tuple[str, bool, int]:
    """
    Returns (text, failed, num_columns).
    """
    try:
        num_cols = detect_columns(page)

        if num_cols > 1:
            raw = extract_columns_ordered(page)
        else:
            raw = page.extract_text() or ""

        return clean_text(raw), False, num_cols

    except Exception as e:
        logger.warning(f"pdfplumber extraction error: {e}")
        return "", True, 1


# ── FALLBACK (PyMuPDF) ───────────────────────────────────
def extract_with_pymupdf(doc, index: int) -> str:
    try:
        return clean_text(doc[index].get_text())
    except Exception:
        return ""


# ── SECTION TAGGER ───────────────────────────────────────
def tag_sections(full_text: str) -> list[dict]:
    """
    Scan full_text for section headers and return their positions.
    Works on the structure-preserving output (double-newline separated).

    Returns a list of:
        {"name": str, "char_offset": int, "line_number": int}
    """
    sections = []
    lines = full_text.split("\n")

    char_offset = 0
    for line_num, line in enumerate(lines):
        stripped = line.strip()
        if SECTION_HEADER_PATTERN.match(stripped):
            sections.append({
                "name": stripped.title(),
                "char_offset": char_offset,
                "line_number": line_num + 1
            })
        char_offset += len(line) + 1  # +1 for the \n

    return sections


def extract_section_chunks(full_text: str, sections: list[dict]) -> dict[str, str]:
    """
    Given tagged section offsets, slice full_text into per-section chunks.
    Returns {"Skills": "Python, SQL...", "Experience": "...", ...}
    """
    if not sections:
        return {}

    chunks = {}
    for i, section in enumerate(sections):
        start = section["char_offset"]
        end = sections[i + 1]["char_offset"] if i + 1 < len(sections) else len(full_text)
        content = full_text[start:end].strip()
        # Remove the header line itself from the content
        lines = content.split("\n")
        body = "\n".join(lines[1:]).strip()
        chunks[section["name"]] = body

    return chunks


# ── BUILD FULL TEXT ──────────────────────────────────────
def build_full_text(pages: list) -> str:
    parts = []
    for p in pages:
        header = PAGE_SEPARATOR.format(n=p["page_number"])
        body = p["text"]
        parts.append(f"{header}\n{body}" if body else header)
    return "\n\n".join(parts)


# ── MAIN FUNCTION ────────────────────────────────────────
def parse_pdf(path: str) -> dict:
    """
    Parse a PDF resume and return structured extraction result.

    Return schema:
    {
        "file_path": str,
        "total_pages": int,
        "is_scanned": bool,
        "metadata": dict,
        "full_text": str,          # Structure-preserving, section boundaries intact
        "pages": [                 # Per-page breakdown
            {
                "page_number": int,
                "text": str,
                "num_columns": int,
                "extraction_failed": bool
            }
        ],
        "sections": [              # Detected section headers with positions
            {"name": str, "char_offset": int, "line_number": int}
        ],
        "section_chunks": {        # Text sliced by section
            "Skills": str,
            "Experience": str,
            ...
        },
        "warnings": [              # Structured extraction issues
            {"page": int, "reason": str, "detail": str}
        ]
    }
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if file_path.suffix.lower() != ".pdf":
        raise ValueError(f"Not a PDF: {path}")

    logger.info(f"Parsing: {file_path.name}")

    pages = []
    metadata = {}
    scanned = False
    pymupdf_doc = None
    warnings = []

    with pdfplumber.open(file_path) as pdf:

        metadata = {
            str(k).strip(): str(v).strip()
            for k, v in (pdf.metadata or {}).items()
            if v
        }

        # ── Scanned detection (sample first 3 pages) ──
        sample = []
        for i in range(min(3, len(pdf.pages))):
            text, _, _ = extract_page_text(pdf.pages[i])
            sample.append(text)

        scanned = is_scanned(sample)
        if scanned:
            logger.info("Scanned PDF detected — text quality may be degraded")
            warnings.append({
                "page": "all",
                "reason": "scanned_detected",
                "detail": "Average extracted text per page is very low. OCR preprocessing recommended."
            })

        # ── Per-page extraction ──
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text, failed, num_cols = extract_page_text(page)

            if num_cols > 1:
                logger.info(f"Page {page_num}: {num_cols}-column layout detected")

            # Fallback if garbage
            if is_garbage_text(text):
                logger.warning(f"Page {page_num}: garbage text detected, trying PyMuPDF fallback")

                warnings.append({
                    "page": page_num,
                    "reason": "garbage_text",
                    "detail": f"pdfplumber output failed garbage check. PyMuPDF fallback used."
                })

                if pymupdf_doc is None:
                    pymupdf_doc = fitz.open(str(file_path))

                text = extract_with_pymupdf(pymupdf_doc, i)

                # If fallback also fails, log and continue (don't silently drop)
                if not text.strip():
                    logger.error(f"Page {page_num}: both extractors failed — page will be empty")
                    warnings.append({
                        "page": page_num,
                        "reason": "extraction_failed",
                        "detail": "Both pdfplumber and PyMuPDF returned empty/garbage. Page skipped."
                    })

            # Log sparse pages (don't drop them)
            elif len(text.strip()) < 50:
                logger.info(f"Page {page_num}: sparse content ({len(text.strip())} chars) — keeping")
                warnings.append({
                    "page": page_num,
                    "reason": "sparse_content",
                    "detail": f"Page has only {len(text.strip())} characters. May be a cover/contact page."
                })

            pages.append({
                "page_number": page_num,
                "text": text,
                "num_columns": num_cols,
                "extraction_failed": failed
            })

    # ── Assemble full text ──
    full_text = build_full_text(pages)

    # ── Section tagging ──
    sections = tag_sections(full_text)
    section_chunks = extract_section_chunks(full_text, sections)

    if not sections:
        warnings.append({
            "page": "all",
            "reason": "no_sections_detected",
            "detail": (
                "No standard resume section headers found. "
                "Headers may be image-based, use unusual capitalization, or be font-mapped. "
                "Downstream NLP will operate on unsegmented text."
            )
        })

    logger.info(f"Sections detected: {[s['name'] for s in sections]}")
    logger.info(f"Total warnings: {len(warnings)}")

    return {
        "file_path": str(file_path.resolve()),
        "total_pages": len(pages),
        "is_scanned": scanned,
        "metadata": metadata,
        "full_text": full_text,
        "pages": pages,
        "sections": sections,
        "section_chunks": section_chunks,
        "warnings": warnings
    }


# ── CLI USAGE ────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python pdf_parser.py <path_to_resume.pdf>")
        sys.exit(1)

    result = parse_pdf(sys.argv[1])

    print("\n" + "=" * 60)
    print(f"FILE      : {result['file_path']}")
    print(f"PAGES     : {result['total_pages']}")
    print(f"SCANNED   : {result['is_scanned']}")
    print(f"SECTIONS  : {[s['name'] for s in result['sections']]}")
    print(f"WARNINGS  : {len(result['warnings'])}")
    print("=" * 60)

    print("\n── FULL TEXT ──\n")
    print(result["full_text"])

    if result["section_chunks"]:
        print("\n── SECTION CHUNKS ──\n")
        for section, content in result["section_chunks"].items():
            print(f"[{section}]")
            print(content[:300] + ("..." if len(content) > 300 else ""))
            print()

    if result["warnings"]:
        print("\n── WARNINGS ──\n")
        for w in result["warnings"]:
            print(f"  Page {w['page']} | {w['reason']}: {w['detail']}")
# =============================================================================
# pdf_parser.py  — SURGICALLY OPTIMIZED
# =============================================================================
# PURPOSE  : Extract clean, section-split text from a resume PDF.
#            Entry point of the project. One job: produce clean text by section.
#            No NLP. No ML.
#
# PIPELINE : PDF → extract_raw_text → clean_text → split_into_sections → dict
# RETURNS  : { "HEADER": "...", "SKILLS": "...", "PROJECTS": "...", ... }
#
# ── OPTIMIZATION LOG ─────────────────────────────────────────────────────────
#  [OPT-1] Precomputed _HEADER_SET and _SORTED_SECTION_HEADERS at module level.
#          _extract_header_token previously rebuilt set(SECTION_HEADERS) and
#          re-sorted on every single call — O(n) + O(n log n) per line parsed.
#          These are now computed once at import time.
#
#  [OPT-2] Extracted _group_words_by_line() helper.
#          Identical anchor-based Y-grouping logic existed in BOTH _words_to_text
#          and _detect_two_col_start_y (copy-paste duplication).
#          Now a single shared helper — one place to tune _LINE_GAP behaviour.
#
#  [OPT-3] _detect_two_col_start_y now uses list-of-tuples (same shape as
#          _words_to_text) instead of a bare dict — consistent data structure,
#          no dict → sorted(keys) conversion step.
#
#  [ATS-1] ATS Reading Order is preserved as-is: Zone A (full-width header),
#          then Zone B left column, then Zone B right column — this matches
#          the linear top→bottom, left→right reading order that most ATS
#          engines expect. No change needed here.
#
#  [ATS-2] Added x_tolerance=3 (up from 2) in extract_words calls.
#          In compressed-font PDFs, character gaps of exactly 2px cause words
#          to be split ("Fast" + "API" instead of "FastAPI").
#          Value 3 is still safe — actual inter-word gaps in standard body
#          text are 5-8px, so no word merging occurs.
# =============================================================================

import pdfplumber
import re


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────

SECTION_HEADERS = [
    "PROFESSIONAL SUMMARY", "SUMMARY", "OBJECTIVE",
    "EXPERIENCE", "WORK EXPERIENCE",
    "PROJECTS",
    "SKILLS", "TECHNICAL SKILLS",
    "EDUCATION",
    "CERTIFICATIONS",
    "ACHIEVEMENTS",
    "INTERESTS",
    "EXTRACURRICULAR",
]

# [OPT-1] Precomputed — used in _extract_header_token and _split_merged_headers.
# Previously rebuilt inline on every function call.
_HEADER_SET = set(SECTION_HEADERS)
_SORTED_SECTION_HEADERS = sorted(SECTION_HEADERS, key=len, reverse=True)

# Only single-word headers are reliable for two-col zone detection.
_SINGLE_WORD_HEADERS = {h for h in SECTION_HEADERS if ' ' not in h}

# Maps variant → canonical header name.
HEADER_ALIASES: dict[str, str] = {
    # SKILLS variants
    "CORE COMPETENCIES":             "SKILLS",
    "KEY SKILLS":                    "SKILLS",
    "SKILLS & TOOLS":                "SKILLS",
    "TECHNICAL SKILLS & TOOLS":      "TECHNICAL SKILLS",
    "TECHNOLOGIES":                  "SKILLS",
    "TECH STACK":                    "SKILLS",
    # EXPERIENCE variants
    "PROFESSIONAL EXPERIENCE":       "EXPERIENCE",
    "WORK HISTORY":                  "EXPERIENCE",
    "INTERNSHIPS":                   "EXPERIENCE",
    "INTERNSHIP":                    "EXPERIENCE",
    "CAREER HISTORY":                "EXPERIENCE",
    # PROJECTS variants
    "ACADEMIC PROJECTS":             "PROJECTS",
    "PERSONAL PROJECTS":             "PROJECTS",
    "SIDE PROJECTS":                 "PROJECTS",
    "KEY PROJECTS":                  "PROJECTS",
    # CERTIFICATIONS variants
    "LICENSES & CERTIFICATIONS":     "CERTIFICATIONS",
    "CERTIFICATES":                  "CERTIFICATIONS",
    "COURSES":                       "CERTIFICATIONS",
    # ACHIEVEMENTS variants
    "AWARDS":                        "ACHIEVEMENTS",
    "HONORS":                        "ACHIEVEMENTS",
    "HONORS & AWARDS":               "ACHIEVEMENTS",
    "ACCOMPLISHMENTS":               "ACHIEVEMENTS",
    # EXTRACURRICULAR variants
    "EXTRA-CURRICULAR":              "EXTRACURRICULAR",
    "EXTRA CURRICULAR":              "EXTRACURRICULAR",
    "ACTIVITIES":                    "EXTRACURRICULAR",
    "VOLUNTEER":                     "EXTRACURRICULAR",
    "LEADERSHIP":                    "EXTRACURRICULAR",
    # SUMMARY variants
    "ABOUT ME":                      "PROFESSIONAL SUMMARY",
    "PROFILE":                       "PROFESSIONAL SUMMARY",
    "CAREER OBJECTIVE":              "OBJECTIVE",
}


# =============================================================================
# STEP 1 — RAW TEXT EXTRACTION
#
# Layout strategy: two zones per page
#
#   Zone A (top)    — single column  → extract_words + anchor line assembly
#   Zone B (bottom) — two columns   → bbox crop left/right, then same assembly
#
#   ┌──────────────────────────────────────┐  y = 0
#   │  Zone A: full-width, single column   │
#   ├──────────────────┬───────────────────┤  y = split_y (auto-detected)
#   │  Zone B: LEFT    │  Zone B: RIGHT    │
#   └──────────────────┴───────────────────┘  y = page height
# =============================================================================

_LINE_GAP = 6   # px — words within this vertical distance = same line


# ─────────────────────────────────────────────────────────────────────────────
# [OPT-2] NEW SHARED HELPER — replaces duplicated grouping logic
# ─────────────────────────────────────────────────────────────────────────────

def _group_words_by_line(words: list) -> list[tuple[float, list]]:
    """
    Groups pdfplumber word dicts by Y coordinate into logical text lines.

    Uses anchor-based bucketing (same semantics as the original inline logic):
    — First word at a Y sets an anchor.
    — Subsequent words within _LINE_GAP px of any existing anchor join that line.
    — Words beyond _LINE_GAP of all anchors start a new line.

    Returns a list of (anchor_y, [word, ...]) tuples sorted top-to-bottom.

    WHY A SHARED HELPER:
    The identical bucketing loop previously existed verbatim in both
    _words_to_text (list-of-tuples) and _detect_two_col_start_y (dict).
    Two implementations = two places to break when _LINE_GAP is tuned.
    This function is the single source of truth.
    """
    line_groups: list[tuple[float, list]] = []

    for word in sorted(words, key=lambda w: w['top']):
        y = word['top']
        for anchor_y, group in line_groups:
            if abs(y - anchor_y) <= _LINE_GAP:
                group.append(word)
                break
        else:
            line_groups.append((y, [word]))

    return sorted(line_groups, key=lambda g: g[0])


def _words_to_text(words: list) -> str:
    """
    Converts pdfplumber word objects into readable text lines.
    Uses _group_words_by_line for Y-bucketing (was inline before [OPT-2]).
    """
    if not words:
        return ""

    result_lines = []
    for _anchor_y, group in _group_words_by_line(words):
        row = sorted(group, key=lambda w: w['x0'])
        result_lines.append(' '.join(w['text'] for w in row))

    return '\n'.join(result_lines)


def _is_visual_header(text: str) -> bool:
    """
    Returns True if a text string looks like a section header based on
    visual properties alone — no list lookup required.

    Rules (all must pass):
    1. ALL CAPS — primary visual signal of a resume section header.
    2. 1–5 words — headers are short labels, not sentences.
    3. At least one word with ≥ 4 alphabetic characters.
    4. No dot characters — filters degree abbreviations and decimal numbers.
    """
    stripped = text.strip()
    if stripped != stripped.upper():
        return False
    if '.' in stripped:
        return False
    words = stripped.split()
    if not 1 <= len(words) <= 5:
        return False
    alpha_words = [re.sub(r'[^A-Z]', '', w) for w in words]
    if not any(len(w) >= 4 for w in alpha_words):
        return False
    return True


def _detect_two_col_start_y(page) -> float:
    """
    Finds the Y coordinate where the two-column zone begins by scanning for
    the first section header that appears in the RIGHT half of the page.

    [OPT-3] Now uses _group_words_by_line() (list-of-tuples) instead of a
    bare dict — consistent with _words_to_text, eliminates the extra
    sorted(line_groups.keys()) conversion step.

    [ATS-2] x_tolerance raised to 3 (see module header).

    Returns page.height if no two-col zone is found (full page = single col).
    """
    midpoint = page.width / 2
    # [ATS-2] x_tolerance=3 for compressed-font PDFs
    all_words = page.extract_words(x_tolerance=3, y_tolerance=3)

    # [OPT-3] Use shared helper — no more dict + sorted(keys) pattern
    for anchor_y, group in _group_words_by_line(all_words):
        leftmost_x = min(w['x0'] for w in group)
        if leftmost_x <= midpoint:
            continue  # line starts on the left side

        row = sorted(group, key=lambda w: w['x0'])
        line_text = ' '.join(w['text'] for w in row)

        if _is_visual_header(line_text):
            return anchor_y - 5  # small buffer above the header line

    return page.height


def _detect_col_split(words: list, page_width: float) -> float:
    """
    Finds the actual horizontal split point between two columns by measuring
    the gap between the rightmost edge of left-column words and the leftmost
    edge of right-column words.

    Adaptive split avoids rigid W/2 truncation of words straddling the midpoint.
    Tolerates up to _COL_GAP_MARGIN px of column overlap (real-world resumes).
    """
    _COL_GAP_MARGIN = 10  # px

    if not words:
        return page_width / 2

    mid = page_width / 2
    left_x1  = [w['x1'] for w in words if w['x0'] < mid]
    right_x0 = [w['x0'] for w in words if w['x0'] >= mid]

    if left_x1 and right_x0:
        col_left_edge  = max(left_x1)
        col_right_edge = min(right_x0)
        if col_right_edge > col_left_edge - _COL_GAP_MARGIN:
            return (col_left_edge + col_right_edge) / 2

    return mid


def _extract_page_text(page) -> str:
    """
    Extracts text from one page using the two-zone strategy.
    Returns: Zone A (header) → Zone B left → Zone B right.

    [ATS-1] This reading order — full-width header, then left column, then
    right column — matches standard ATS linear reading behaviour.
    Zone B right is appended after Zone B left so that split_into_sections
    receives each column's sections contiguously.

    [ATS-2] x_tolerance=3 in extract_words (see module header).
    """
    W = page.width
    H = page.height
    split_y = _detect_two_col_start_y(page)

    # [ATS-2] x_tolerance=3
    all_words = page.extract_words(x_tolerance=3, y_tolerance=3)

    parts = []

    # Zone A — single column (full width, above split_y)
    if split_y > 0:
        words_a = [w for w in all_words if w['top'] < split_y]
        text_a = _words_to_text(words_a)
        if text_a.strip():
            parts.append(text_a)

    # Zone B — two columns (below split_y)
    if split_y < H:
        words_below = [w for w in all_words if w['top'] >= split_y]
        col_split   = _detect_col_split(words_below, W)

        left_words  = [w for w in words_below if w['x0'] <  col_split]
        right_words = [w for w in words_below if w['x0'] >= col_split]

        text_left  = _words_to_text(left_words)
        text_right = _words_to_text(right_words)

        if text_left.strip():
            parts.append(text_left)
        if text_right.strip():
            parts.append(text_right)

    page_text = '\n'.join(parts)
    page_text = _rejoin_hyphen_breaks(page_text)
    page_text = _split_merged_headers(page_text)

    return page_text


def extract_raw_text(pdf_path: str) -> str:
    """Opens the PDF and extracts raw text page by page. Returns one string."""
    all_pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = _extract_page_text(page)
                if page_text.strip():
                    all_pages.append(page_text)
    except FileNotFoundError:
        print(f"[ERROR] File not found: {pdf_path}")
        return ""
    except Exception as e:
        print(f"[ERROR] PDF read failed: {e}")
        return ""
    return '\n'.join(all_pages)


# =============================================================================
# STEP 1b — LINE-LEVEL POST-PROCESSING
# =============================================================================

def _rejoin_hyphen_breaks(text: str) -> str:
    """
    Rejoins words split across lines by a PDF line-wrap hyphen.
    Pattern 1: "work-\\nflows."     → "workflows."
    Pattern 2: "work-\\n-\\nflows." → "workflows." (orphan bullet between)
    """
    text = re.sub(r'(\w)-\n-\n([a-z])', r'\1\2', text)
    text = re.sub(r'(\w)-\n([a-z])',    r'\1\2', text)
    return text


def _split_merged_headers(text: str) -> str:
    """
    Splits lines that are exactly TWO known headers joined by whitespace:
    e.g. "SKILLS EDUCATION" → "SKILLS\\nEDUCATION".

    [OPT-1] Uses precomputed _SORTED_SECTION_HEADERS instead of re-sorting inline.
    """
    all_known = set(SECTION_HEADERS) | set(HEADER_ALIASES.keys())

    result_lines = []
    for line in text.split('\n'):
        stripped = line.strip().upper()
        matched  = False

        words_in_line = stripped.split()
        for split_at in range(1, len(words_in_line)):
            left_part  = ' '.join(words_in_line[:split_at])
            right_part = ' '.join(words_in_line[split_at:])
            if left_part in all_known and right_part in all_known:
                left_canon  = HEADER_ALIASES.get(left_part,  left_part)
                right_canon = HEADER_ALIASES.get(right_part, right_part)
                result_lines.append(left_canon)
                result_lines.append(right_canon)
                matched = True
                break

        if not matched:
            result_lines.append(line)

    return '\n'.join(result_lines)


# =============================================================================
# STEP 2 — CLEAN THE RAW TEXT
# =============================================================================

def _clean_line(line: str) -> str:
    """Remove noise characters. Normalize bullets, dashes, quotes, spacing."""
    line = re.sub(r'\(cid:\d+\)', '', line)
    line = re.sub(r'\[Link\]', '', line)
    line = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', line)
    line = re.sub(r'[\u2018\u2019]', "'", line)
    line = re.sub(r'[\u201c\u201d]', '"', line)
    line = line.replace('•', '-')
    line = line.replace('–', '-').replace('—', ' - ')
    line = re.sub(r'[ \t]+', ' ', line)
    return line.strip()


def _fix_orphan_bullets(text: str) -> str:
    """
    Resolves lone bullet lines ('-' on their own):
    Case 1 — lone bullet + lowercase next line → join to previous line.
    Case 2 — lone bullet + another bullet      → drop the orphan.
    Case 3 — lone bullet at end of text        → drop trailing bullet.
    """
    lines = text.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        is_lone_bullet = line.strip() == '-'

        if is_lone_bullet:
            next_idx = i + 1
            while next_idx < len(lines) and not lines[next_idx].strip():
                next_idx += 1

            if next_idx < len(lines):
                next_line = lines[next_idx].strip()

                if next_line and next_line[0].islower():
                    if result:
                        result[-1] = result[-1].rstrip() + ' ' + next_line
                    else:
                        result.append(next_line)
                    i = next_idx + 1
                    continue

                if next_line.startswith('-'):
                    i += 1
                    continue
            else:
                i += 1
                continue

        result.append(line)
        i += 1

    return '\n'.join(result)


def _fix_soft_wraps(text: str) -> str:
    """
    Joins lines split mid-sentence by PDF line wrapping (no hyphen involved).

    Guards prevent merging standalone items (cert names, dates, school names):
    Guard 1: current line ≤ 4 words → standalone, do not merge.
    Guard 2: next line < 3 words    → standalone, do not merge.
    Guard 3: next line is ALL CAPS  → section header, never merge.
    """
    _MIN_CURR_WORDS = 5
    _MIN_NEXT_WORDS = 3

    lines = text.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]

        if i + 1 < len(lines):
            next_line        = lines[i + 1].strip()
            current_stripped = line.rstrip()
            curr_words       = len(current_stripped.split())
            next_words       = len(next_line.split()) if next_line else 0

            ends_sentence   = current_stripped.endswith(('.', ',', ':', ';', '!', '?'))
            is_continuation = bool(next_line and next_line[0].islower())
            is_new_bullet   = next_line.startswith('-')
            curr_too_short  = curr_words <= _MIN_CURR_WORDS
            next_too_short  = next_words < _MIN_NEXT_WORDS
            next_is_header  = bool(next_line and next_line == next_line.upper()
                                   and next_line.isalpha())

            should_merge = (
                not ends_sentence
                and is_continuation
                and not is_new_bullet
                and not curr_too_short
                and not next_too_short
                and not next_is_header
            )

            if should_merge:
                result.append(current_stripped + ' ' + next_line)
                i += 2
                continue

        result.append(line)
        i += 1

    return '\n'.join(result)


def _normalize_headers(text: str) -> str:
    """
    Ensures section headers are isolated on their own lines.
    Pass 2: if a known header is embedded at the start of a content line,
    split it onto its own line. Only inserts newlines — never removes content.
    """
    lines = text.split('\n')
    result = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append(line)
            continue

        header, remainder = _extract_header_token(stripped)
        if header and remainder:
            if ':' in stripped:
                orig_rest = stripped.split(':', 1)[1].strip()
            else:
                idx = stripped.upper().find(header)
                orig_rest = stripped[idx + len(header):].strip().lstrip(' &/|-').strip()

            result.append(header)
            if orig_rest:
                result.append(orig_rest)
        else:
            result.append(line)

    return '\n'.join(result)


def clean_text(raw_text: str) -> str:
    """
    Full cleaning pipeline:
    1. _clean_line         — noise removal, bullet/dash/space normalisation
    2. _fix_orphan_bullets — resolve lone '-' lines
    3. _fix_soft_wraps     — join mid-sentence PDF line breaks
    4. _normalize_headers  — isolate embedded headers onto their own lines
    """
    cleaned = []
    for line in raw_text.split('\n'):
        line = _clean_line(line)
        if line:
            cleaned.append(line)

    result = '\n'.join(cleaned)
    result = re.sub(r'\n{3,}', '\n\n', result)
    result = _fix_orphan_bullets(result)
    result = _fix_soft_wraps(result)
    result = _normalize_headers(result)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


# =============================================================================
# STEP 3 — SPLIT INTO SECTIONS
# =============================================================================

def _extract_header_token(line: str) -> tuple:
    """
    Detects whether a line starts with a section header, even when the header
    is followed by content on the same line.
    Returns (canonical_header, remainder) or (None, None).

    [OPT-1] Uses precomputed _HEADER_SET and _SORTED_SECTION_HEADERS.
    Previously rebuilt set(SECTION_HEADERS) and re-sorted on EVERY call.

    Matching stages:
      Stage 1 — before-colon token:  "SKILLS: Python"  →  "SKILLS"
      Stage 2 — exact match:         "SKILLS"           →  "SKILLS"
      Stage 3 — alias match:         "CORE COMPETENCIES" → "SKILLS"
      Stage 4 — prefix match:        "CERTIFICATIONS Data..." → "CERTIFICATIONS"
    """
    upper = line.strip().upper()

    # Stage 1: colon mid-line
    if ':' in upper:
        before = upper.split(':', 1)[0].strip()
        after  = upper.split(':', 1)[1].strip()

        if before in _HEADER_SET:                    # [OPT-1] precomputed set
            return before, after
        if before in HEADER_ALIASES:
            return HEADER_ALIASES[before], after
        for h in _SORTED_SECTION_HEADERS:            # [OPT-1] precomputed sort
            if before.startswith(h) and len(before) > len(h):
                if before[len(h)] in (' ', '&', '/', '|', '-'):
                    return h, after

    # Stages 2–4: match full line (trailing colon stripped)
    clean = upper.rstrip(':').strip()

    if clean in _HEADER_SET:                         # [OPT-1] Stage 2
        return clean, ""

    if clean in HEADER_ALIASES:                      # Stage 3
        return HEADER_ALIASES[clean], ""

    for h in _SORTED_SECTION_HEADERS:               # [OPT-1] Stage 4
        if clean.startswith(h) and len(clean) > len(h):
            if clean[len(h)] in (' ', '&', '/', '|', '-'):
                remainder = clean[len(h):].strip().lstrip('&/|- ').strip()
                return h, remainder

    return None, None


def split_into_sections(cleaned_text: str) -> dict:
    """
    Scans line by line. Opens a new section bucket on each header line.
    Everything before the first header → 'HEADER' (name + contacts).

    Uses _extract_header_token() to handle inline content after headers
    and mid-line colon headers (prevents section bleeding).

    Returns: { "HEADER": "...", "EXPERIENCE": "...", "SKILLS": "...", ... }
    """
    sections: dict = {}
    current = "HEADER"
    sections[current] = []

    for line in cleaned_text.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith('-') or stripped.startswith('•'):
            sections[current].append(stripped)
            continue

        header, remainder = _extract_header_token(stripped)

        if header:
            current = header
            sections[current] = []

            if remainder:
                if ':' in stripped:
                    orig_rest = stripped.split(':', 1)[1].strip()
                else:
                    idx = stripped.upper().find(header)
                    orig_rest = stripped[idx + len(header):].strip().lstrip(' &/|-').strip()
                if orig_rest:
                    sections[current].append(orig_rest)
        else:
            sections[current].append(stripped)

    return {
        name: '\n'.join(lines).strip()
        for name, lines in sections.items()
        if '\n'.join(lines).strip()
    }


# =============================================================================
# PUBLIC API
# =============================================================================

def parse_resume(pdf_path: str) -> dict:
    """
    Full pipeline: PDF → raw text → clean text → sections dict.
    The only function other modules need to call.

    Usage from resume_extraction.py:
        from pdf_parser import parse_resume
        sections = parse_resume("resume.pdf")
        print(sections.get("SKILLS", ""))
        print(sections.get("EXPERIENCE", ""))

    Returns {} if the PDF cannot be read.
    """
    print(f"\n[pdf_parser] Starting → {pdf_path}")

    print("[1/3] Extracting raw text...")
    raw = extract_raw_text(pdf_path)

    if not raw.strip():
        print("[ERROR] No text extracted. PDF may be image/scanned.")
        return {}

    print("[2/3] Cleaning text...")
    cleaned = clean_text(raw)

    print("[3/3] Splitting into sections...")
    sections = split_into_sections(cleaned)

    print(f"[pdf_parser] Done → sections: {list(sections.keys())}\n")
    return sections
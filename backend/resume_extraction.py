# =============================================================================
# resume_extraction.py
# =============================================================================
# PURPOSE  : Convert raw section text from pdf_parser into structured JSON.
#            Rule-based parsing with an optional semantic matching layer
#            for gap analysis and synonym-aware skill comparison.
#
# PIPELINE : sections_dict → structured_json
# INPUT    : { "SKILLS": "...", "EXPERIENCE": "...", ... }  ← from pdf_parser
# OUTPUT   : { "skills": [], "experience": [], "education": [], "projects": [] }
#
# ── SEMANTIC LAYER NOTE ───────────────────────────────────────────────────────
# The semantic functions (semantic_skill_match, find_missing_skills) use a
# pre-trained sentence-transformer model. This is NOT an LLM API call — it is
# a deterministic embedding lookup that maps text → fixed-size float vectors.
# No training occurs at runtime. The model runs locally, offline, in ~50ms.
#
# Install once:  pip install sentence-transformers
# Model used:    all-MiniLM-L6-v2  (80MB, fast, accurate for skill similarity)
# =============================================================================

import re
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# SECTION KEY LOOKUP (pdf_parser outputs ALL-CAPS keys)
# ─────────────────────────────────────────────────────────────────────────────

_SKILLS_KEYS     = ["SKILLS", "TECHNICAL SKILLS"]
_EXPERIENCE_KEYS = ["EXPERIENCE", "WORK EXPERIENCE"]
_EDUCATION_KEYS  = ["EDUCATION"]
_PROJECTS_KEYS   = ["PROJECTS"]


def _get_section(sections: dict, keys: list) -> str:
    """Return the first non-empty section value matching any of the given keys."""
    for key in keys:
        val = sections.get(key, "").strip()
        if val:
            return val
    return ""


# =============================================================================
# RULE-BASED PARSERS (no AI — pipeline constraint)
# =============================================================================

# Pre-compiled patterns — compiled once at import, not per call

# Matches skill section category labels in two formats:
#   Format A (colon)     → "Languages:", "Web/App:", "DS/AI:"
#   Format B (no colon)  → "Technical Skills SQL", "Analytical Skills Data"
#                           Label detected by known prefix words + space + content.
#
# Format B uses a named group of known category words so we don't accidentally
# strip real skill names like "Python" or "Machine Learning".
_SKILL_CATEGORY_LABEL = re.compile(
    r'^(?:'
    r'[A-Za-z \/&]+\s*:'                                # Format A: any label + colon
    r'|'
    r'(?:Technical|Analytical|Soft|Core|Professional|'  # Format B: known prefix words
    r'Web|App|Languages?|Databases?|Frameworks?|Tools?|DS|AI)\s+(?:Skills?|Tools?|Stack)?\s+'
    r')',
    re.MULTILINE | re.IGNORECASE
)
_SKILL_DELIMITERS = re.compile(r'[,\n|•]+')
_BULLET_PREFIX    = re.compile(r'^-+\s*')


def _parse_skills(raw: str) -> list:
    """
    Splits skills text into individual skill tokens.

    Handles:
    - Category labels    → "Languages: Python, SQL"  →  ["Python", "SQL"]
    - Comma-separated    → "React, Node.js, REST APIs"
    - Newline-separated  → one skill per line
    - Bullet-prefixed    → "- Python\n- SQL"
    - Pipe-delimited     → "Python | SQL | React"

    Deduplicates preserving first-occurrence order (case-insensitive).
    """
    # Strip category labels ("Languages:", "Technical Skills:", etc.)
    raw = _SKILL_CATEGORY_LABEL.sub('', raw)

    # Split by all common delimiters
    tokens = _SKILL_DELIMITERS.split(raw)

    skills = []
    for token in tokens:
        # Remove any leading bullet/dash artifact
        token = _BULLET_PREFIX.sub('', token).strip()
        # Filter noise: empty, single characters, stray punctuation
        if token and len(token) > 1 and not token.isdigit():
            skills.append(token)

    # Deduplicate preserving order
    seen: set = set()
    unique = []
    for s in skills:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def _parse_bullets(raw: str) -> list:
    """
    Extracts bullet points and role/company headers from an EXPERIENCE or
    PROJECTS section.

    Strategy:
    - Lines starting with '-' → bullet content (strip the dash).
    - Short lines (≤ 4 words, no dash) → label/header (company, role, date).
      These are kept as-is so the evaluator has full context.
    - Longer non-bullet lines → treated as continuation of previous bullet
      if previous exists, otherwise kept as a standalone entry.

    Returns a flat list of strings: mix of headers and bullet texts.
    """
    lines = [l.strip() for l in raw.split('\n') if l.strip()]
    result = []
    current_bullet: Optional[str] = None

    for line in lines:
        is_bullet = line.startswith('-')

        if is_bullet:
            # Flush any pending bullet before starting a new one
            if current_bullet is not None:
                result.append(current_bullet)
            current_bullet = _BULLET_PREFIX.sub('', line).strip()

        else:
            word_count = len(line.split())

            if word_count <= 4:
                # Short line = label/header (company, date, title)
                if current_bullet is not None:
                    result.append(current_bullet)
                    current_bullet = None
                result.append(line)
            else:
                # Long non-bullet line
                if current_bullet is not None:
                    # Likely soft-wrap continuation not caught by parser
                    current_bullet += ' ' + line
                else:
                    # Standalone sentence (no preceding bullet)
                    result.append(line)

    # Flush the last pending bullet
    if current_bullet is not None:
        result.append(current_bullet)

    return [r for r in result if r]


def _parse_education(raw: str) -> list:
    """
    Extracts education entries.

    Education sections are typically structured as short labeled lines
    (degree, institution, CGPA, year). Returns each non-empty, de-bulleted line.
    """
    lines = []
    for line in raw.split('\n'):
        line = _BULLET_PREFIX.sub('', line).strip()
        if line:
            lines.append(line)
    return lines


# =============================================================================
# SEMANTIC MATCHING LAYER
# =============================================================================
# Uses sentence-transformers to compute cosine similarity between skill strings.
# This allows matching synonyms and related terms the keyword approach misses:
#
#   "FastAPI"         ≈  "REST API framework"      (score ≈ 0.71)
#   "Redux"           ≈  "state management"         (score ≈ 0.68)
#   "Scikit-learn"    ≈  "machine learning library" (score ≈ 0.74)
#   "Firebase"        ≈  "NoSQL cloud database"     (score ≈ 0.65)
#
# The model is loaded lazily — only on the first call that needs it.
# Subsequent calls reuse the singleton (no repeated disk I/O).
# =============================================================================

_encoder = None   # Singleton — loaded once per process


def _get_encoder():
    """
    Lazily load the sentence-transformer model.

    Returns the SentenceTransformer instance if available, or None if the
    package is not installed. Marks the encoder as False after a failed
    import so we don't retry on every subsequent call.
    """
    global _encoder
    if _encoder is None:
        try:
            from sentence_transformers import SentenceTransformer
            print("[resume_extraction] Loading semantic encoder (once per process)...")
            _encoder = SentenceTransformer("all-MiniLM-L6-v2")
            print("[resume_extraction] Encoder ready.")
        except ImportError:
            print(
                "[resume_extraction] WARNING: sentence-transformers not installed.\n"
                "  Semantic matching will fall back to substring matching.\n"
                "  Install with:  pip install sentence-transformers"
            )
            _encoder = False   # Sentinel — do not retry
    return _encoder if _encoder is not False else None


def _cosine_similarity_matrix(a, b):
    """
    Vectorised cosine similarity between two numpy arrays.
    a: shape (m, d), b: shape (n, d)  →  returns matrix of shape (m, n).
    """
    import numpy as np
    a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-10)
    b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
    return a_norm @ b_norm.T


def semantic_skill_match(
    resume_skills: list,
    target_skills: list,
    threshold: float = 0.62,
) -> list:
    """
    Find semantically similar pairs between resume skills and a target list.

    Args:
        resume_skills:  Skills extracted from the resume (from extract_resume).
        target_skills:  Skills from the job description or a standard taxonomy.
        threshold:      Cosine similarity cutoff in [0, 1].
                        0.62 is intentionally permissive to catch synonyms.
                        Raise to 0.75+ for stricter exact-match behaviour.

    Returns:
        List of dicts sorted by descending similarity:
        [{ "resume_skill": str, "target_skill": str, "score": float }, ...]
        Only pairs at or above threshold are returned.

    Fallback (sentence-transformers not installed):
        Case-insensitive substring matching — score is always 1.0.
    """
    if not resume_skills or not target_skills:
        return []

    encoder = _get_encoder()

    # ── Fallback: substring matching ──────────────────────────────────────────
    if encoder is None:
        matches = []
        for rs in resume_skills:
            for ts in target_skills:
                if rs.lower() in ts.lower() or ts.lower() in rs.lower():
                    matches.append({
                        "resume_skill":  rs,
                        "target_skill":  ts,
                        "score":         1.0,
                    })
        return matches

    # ── Semantic matching ─────────────────────────────────────────────────────
    src_emb = encoder.encode(resume_skills, convert_to_numpy=True, show_progress_bar=False)
    tgt_emb = encoder.encode(target_skills, convert_to_numpy=True, show_progress_bar=False)

    sim_matrix = _cosine_similarity_matrix(src_emb, tgt_emb)  # (m, n)

    matches = []
    for i, rs in enumerate(resume_skills):
        for j, ts in enumerate(target_skills):
            score = float(sim_matrix[i, j])
            if score >= threshold:
                matches.append({
                    "resume_skill": rs,
                    "target_skill": ts,
                    "score":        round(score, 3),
                })

    return sorted(matches, key=lambda x: x["score"], reverse=True)


def find_missing_skills(
    resume_skills: list,
    target_skills: list,
    threshold: float = 0.62,
) -> list:
    """
    Return target skills NOT covered by any resume skill above the threshold.

    A target skill is considered 'covered' if at least one resume skill is
    semantically similar to it (score ≥ threshold).

    This is the primary gap analysis function — call it from ai_evaluator.py
    when a job description is available:

        from resume_extraction import find_missing_skills
        gaps = find_missing_skills(structured["skills"], jd_skills)

    Args:
        resume_skills: Skills from the resume.
        target_skills: Required skills from a job description or taxonomy.
        threshold:     Same cosine cutoff as semantic_skill_match.

    Returns:
        List of target skills not matched by any resume skill.
    """
    if not target_skills:
        return []
    if not resume_skills:
        return target_skills[:]

    matched_targets = {
        m["target_skill"]
        for m in semantic_skill_match(resume_skills, target_skills, threshold)
    }
    return [ts for ts in target_skills if ts not in matched_targets]


# =============================================================================
# PUBLIC API
# =============================================================================

def extract_resume(sections: dict) -> dict:
    """
    Convert raw sections dict (from pdf_parser.parse_resume) into structured JSON.

    Args:
        sections: Output of pdf_parser.parse_resume()
                  e.g. { "SKILLS": "Python, SQL...", "EXPERIENCE": "- Built..." }

    Returns:
        {
            "skills":     [str, ...],   # individual skill tokens
            "experience": [str, ...],   # bullet points + role/company labels
            "education":  [str, ...],   # education entry lines
            "projects":   [str, ...]    # bullet points + project title labels
        }

    Usage:
        from pdf_parser import parse_resume
        from resume_extraction import extract_resume

        sections  = parse_resume("resume.pdf")
        structured = extract_resume(sections)

        # Semantic gap analysis (requires sentence-transformers):
        from resume_extraction import find_missing_skills
        jd_skills = ["Docker", "Kubernetes", "CI/CD", "REST APIs"]
        gaps = find_missing_skills(structured["skills"], jd_skills)
    """
    return {
        "skills":     _parse_skills(_get_section(sections, _SKILLS_KEYS)),
        "experience": _parse_bullets(_get_section(sections, _EXPERIENCE_KEYS)),
        "education":  _parse_education(_get_section(sections, _EDUCATION_KEYS)),
        "projects":   _parse_bullets(_get_section(sections, _PROJECTS_KEYS)),
    }
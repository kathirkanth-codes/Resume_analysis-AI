# =============================================================================
# resume_extraction.py
# =============================================================================
# PURPOSE  : Convert raw section text from pdf_parser into structured JSON.
#            Primary path  : Groq LLM  — semantic, format-agnostic, works on
#                            any resume layout without fragile rules.
#            Fallback path : Rule-based parsing — activates automatically
#                            when the LLM call fails (quota, network, etc.).
#
# PIPELINE : sections_dict → structured_json
# INPUT    : { "SKILLS": "...", "EXPERIENCE": "...", ... }  ← from pdf_parser
# OUTPUT   : { "skills": [], "experience": [], "education": [], "projects": [] }
#
# REQUIRES : pip install groq python-dotenv
# API KEY  : GROQ_API_KEY in backend/.env
# =============================================================================

import os
import re
import json
from typing import Optional
from dotenv import load_dotenv
from groq import Groq

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

_MODEL  = "llama-3.3-70b-versatile"
_CLIENT = Groq(api_key=os.getenv("GROQ_API_KEY"))


# =============================================================================
# LLM-BASED EXTRACTION — PRIMARY PATH
# =============================================================================

def _build_extraction_prompt(sections: dict) -> str:
    """
    Assemble the prompt from all non-HEADER sections.
    HEADER contains only name/contact info and adds noise without value.
    """
    relevant = {k: v for k, v in sections.items() if k != "HEADER" and v.strip()}
    if not relevant:
        return ""

    blocks = [f"[{section}]\n{content.strip()}" for section, content in relevant.items()]
    resume_text = "\n\n".join(blocks)

    return f"""Extract structured data from this resume. Return ONLY valid JSON — no markdown, no explanation.

RESUME:
{resume_text}

---

INSTRUCTIONS:

skills:
- Return a flat list of individual skill names (languages, frameworks, tools, concepts)
- Split categorised lists: "Languages: Python, SQL" → ["Python", "SQL"]
- Do NOT include category label words like "Languages" or "Frameworks"
- No duplicates

experience:
- One entry per internship, job, or work placement
- company: organisation name only
- role: job title only
- duration: date range as written (e.g. "Jun 2024 - Aug 2024"), or "" if absent
- bullets: list of achievement/responsibility descriptions — plain text, no leading dashes

education:
- One entry per degree, diploma, or school level
- degree: full degree name and specialisation
- institution: school/university/college name only
- grade: CGPA or percentage as a plain number string (e.g. "8.5" or "78.2"), or ""
- year: 4-digit graduation or expected year, or ""

projects:
- One entry per distinct project
- title: project name only
- duration: date range if present, else ""
- bullets: list of description points — plain text, no leading dashes

Return exactly this JSON shape:
{{
  "skills": ["skill1", "skill2"],
  "experience": [
    {{"company": "...", "role": "...", "duration": "...", "bullets": ["..."]}}
  ],
  "education": [
    {{"degree": "...", "institution": "...", "grade": "...", "year": ""}}
  ],
  "projects": [
    {{"title": "...", "duration": "...", "bullets": ["..."]}}
  ]
}}"""


def _validate_and_clean(data: dict) -> dict:
    """
    Coerce the LLM response into the exact shape the rest of the pipeline expects.
    Fills in defaults for any missing or malformed fields so downstream never breaks.
    """
    def to_str_list(lst) -> list:
        if not isinstance(lst, list):
            return []
        return [str(x).strip() for x in lst if x and str(x).strip()]

    def clean_exp(e) -> Optional[dict]:
        if not isinstance(e, dict):
            return None
        return {
            "company":  str(e.get("company")  or "").strip(),
            "role":     str(e.get("role")     or "").strip(),
            "duration": str(e.get("duration") or "").strip(),
            "bullets":  to_str_list(e.get("bullets", [])),
        }

    def clean_edu(e) -> Optional[dict]:
        if not isinstance(e, dict):
            return None
        return {
            "degree":      str(e.get("degree")      or "").strip(),
            "institution": str(e.get("institution") or "").strip(),
            "grade":       str(e.get("grade")       or "").strip(),
            "year":        str(e.get("year")        or "").strip(),
        }

    def clean_proj(e) -> Optional[dict]:
        if not isinstance(e, dict):
            return None
        return {
            "title":    str(e.get("title")    or "").strip(),
            "duration": str(e.get("duration") or "").strip(),
            "bullets":  to_str_list(e.get("bullets", [])),
        }

    return {
        "skills":     to_str_list(data.get("skills", [])),
        "experience": [x for x in (clean_exp(e)  for e in data.get("experience", [])) if x],
        "education":  [x for x in (clean_edu(e)  for e in data.get("education",  [])) if x],
        "projects":   [x for x in (clean_proj(e) for e in data.get("projects",   [])) if x],
    }


def _empty_result() -> dict:
    return {"skills": [], "experience": [], "education": [], "projects": []}


# =============================================================================
# RULE-BASED EXTRACTION — FALLBACK PATH
# =============================================================================
# Activated automatically when the Groq call fails (quota, network, bad JSON).
# Handles the common well-formatted resume layouts reliably.
# =============================================================================

# Section key variants — pdf_parser may output any of these
_SKILLS_KEYS     = ["SKILLS", "TECHNICAL SKILLS"]
_EXPERIENCE_KEYS = ["EXPERIENCE", "WORK EXPERIENCE"]
_EDUCATION_KEYS  = ["EDUCATION"]
_PROJECTS_KEYS   = ["PROJECTS"]

_SKILL_CATEGORY_LABEL = re.compile(
    r'^(?:'
    r'[A-Za-z \/&]+\s*:'
    r'|'
    r'(?:Technical|Analytical|Soft|Core|Professional|'
    r'Web|App|Languages?|Databases?|Frameworks?|Tools?|DS|AI)\s*(?:Skills?|Tools?|Stack)?\s+'
    r')',
    re.MULTILINE | re.IGNORECASE
)
_SKILL_DELIMITERS = re.compile(r'[,\n|•]+')
_BULLET_PREFIX    = re.compile(r'^-+\s*')
_DATE_PATTERN     = re.compile(
    r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*'
    r'[\s\'\-]?\d{2,4}'
    r'(?:\s*[-–]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*'
    r'[\s\']?\d{0,4}|[-–]\s*(?:Present|Current|present|current))?',
    re.IGNORECASE
)

_ACTION_VERBS = {
    'built', 'developed', 'designed', 'created', 'implemented', 'worked',
    'integrated', 'deployed', 'engineered', 'collaborated', 'performed',
    'identified', 'completed', 'customized', 'managed', 'led', 'delivered',
    'optimized', 'automated', 'analyzed', 'produced', 'maintained',
    'improved', 'resolved', 'supported', 'tested', 'configured', 'launched',
    'reduced', 'increased', 'streamlined', 'migrated', 'established',
    'solved', 'achieved', 'contributed', 'spearheaded', 'coordinated',
    'assisted', 'attended', 'used', 'utilized', 'applied', 'handled',
    'gathered', 'collected', 'extracted', 'processed', 'prepared',
    'presented', 'reviewed', 'updated', 'refactored', 'fixed', 'added',
    'wrote', 'conducted', 'monitored', 'tracked', 'documented', 'evaluated',
    'trained', 'administered', 'installed', 'helped', 'made',
    'converted', 'transformed', 'generated', 'constructed', 'executed',
    'modified', 'validated', 'verified', 'enabled', 'enhanced',
}


def _get_section(sections: dict, keys: list) -> str:
    for key in keys:
        val = sections.get(key, "").strip()
        if val:
            return val
    return ""


def _parse_skills(raw: str) -> list:
    lines_clean = [_BULLET_PREFIX.sub('', ln).strip() for ln in raw.split('\n')]
    raw = '\n'.join(lines_clean)
    raw = _SKILL_CATEGORY_LABEL.sub('', raw)
    tokens = _SKILL_DELIMITERS.split(raw)
    skills = []
    for token in tokens:
        token = _BULLET_PREFIX.sub('', token).strip()
        if token and len(token) > 1 and not token.isdigit():
            skills.append(token)
    seen: set = set()
    unique = []
    for s in skills:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            unique.append(s)
    return unique


def _is_entry_header(line: str) -> bool:
    clean = _BULLET_PREFIX.sub('', line).strip()
    if not clean:
        return False
    if _DATE_PATTERN.search(clean):
        return True
    if len(clean) > 80:
        return False
    if re.search(r'\d+\s*[+%]|\d{1,3},\d{3}', clean):
        return False
    first_word = clean.split()[0].lower().rstrip('.,;:()')
    if first_word in _ACTION_VERBS:
        return False
    if clean.endswith(('.', '!', '?')):
        return False
    return True


def _split_exp_header(raw_header: str) -> dict:
    date_match = _DATE_PATTERN.search(raw_header)
    duration   = date_match.group(0).strip() if date_match else ""
    base       = raw_header[:date_match.start()].strip() if date_match else raw_header
    base       = re.sub(r'\s*\([^)]*\)', '', base).strip().rstrip(' -')
    parts      = re.split(r'\s+-\s+', base, maxsplit=1)
    return {
        "company":  parts[0].strip(),
        "role":     parts[1].strip() if len(parts) > 1 else "",
        "duration": duration,
        "bullets":  [],
    }


def _split_proj_header(raw_header: str) -> dict:
    date_match = _DATE_PATTERN.search(raw_header)
    duration   = date_match.group(0).strip() if date_match else ""
    title      = raw_header[:date_match.start()].strip() if date_match else raw_header
    return {"title": title.rstrip(' -').strip(), "duration": duration, "bullets": []}


def _parse_grouped_entries(raw: str, mode: str) -> list:
    entries = []
    current = None

    for line in raw.split('\n'):
        line = line.strip()
        if not line:
            continue

        if line.startswith('-'):
            clean = _BULLET_PREFIX.sub('', line).strip()
            if _is_entry_header(line):
                if current is not None:
                    entries.append(current)
                current = (
                    _split_exp_header(clean) if mode == 'experience'
                    else _split_proj_header(clean)
                )
            else:
                if current is None:
                    current = (
                        {'company': '', 'role': '', 'duration': '', 'bullets': []}
                        if mode == 'experience' else
                        {'title': '', 'duration': '', 'bullets': []}
                    )
                current['bullets'].append(clean)
        else:
            if _DATE_PATTERN.search(line):
                if current is not None:
                    entries.append(current)
                current = (
                    _split_exp_header(line) if mode == 'experience'
                    else _split_proj_header(line)
                )
            elif (current is not None and current['bullets']
                  and line and line[0].islower() and len(line.split()) >= 3):
                current['bullets'][-1] += ' ' + line
            elif len(line.split()) >= 7:
                if current is None:
                    current = (
                        {'company': '', 'role': '', 'duration': '', 'bullets': []}
                        if mode == 'experience' else
                        {'title': '', 'duration': '', 'bullets': []}
                    )
                current['bullets'].append(line)

    if current is not None:
        entries.append(current)

    return [e for e in entries if e]


def _parse_education_structured(raw: str) -> list:
    entries = []
    current = None

    for line in raw.split('\n'):
        line = _BULLET_PREFIX.sub('', line).strip()
        if not line:
            continue

        grade_match = re.search(r'(\d+\.?\d*)\s*%|CGPA\s*[:\-]?\s*(\d+\.?\d*)', line, re.IGNORECASE)
        year_match  = re.search(r'\b(20\d{2})\b', line)
        is_school   = any(w in line.lower() for w in ['university', 'institute', 'college', 'school', 'academy'])
        is_degree   = any(w in line.upper() for w in [
            'B.E', 'B.TECH', 'M.E', 'M.TECH', 'BSC', 'MSC', 'MBA', 'CSE',
            'SECONDARY', 'CBSE', 'BACHELOR', 'MASTER', 'ENGINEERING',
            'DIPLOMA', 'STANDARD', 'B.SC', 'M.SC', 'PHD', 'DOCTORATE',
        ])

        if grade_match and current:
            current['grade'] = grade_match.group(1) or grade_match.group(2)
            if year_match:
                current['year'] = year_match.group(1)
        elif is_school and current:
            current['institution'] = line
        elif is_degree or (not is_school and not grade_match and len(line.split()) <= 4):
            if current:
                entries.append(current)
            current = {
                'degree':      line,
                'institution': '',
                'grade':       '',
                'year':        year_match.group(1) if year_match else '',
            }

    if current:
        entries.append(current)

    return [e for e in entries if e['degree']]


def _extract_resume_rule_based(sections: dict) -> dict:
    """Rule-based fallback. Used when LLM is unavailable."""
    return {
        "skills":     _parse_skills(_get_section(sections, _SKILLS_KEYS)),
        "experience": _parse_grouped_entries(_get_section(sections, _EXPERIENCE_KEYS), mode='experience'),
        "education":  _parse_education_structured(_get_section(sections, _EDUCATION_KEYS)),
        "projects":   _parse_grouped_entries(_get_section(sections, _PROJECTS_KEYS), mode='project'),
    }


# =============================================================================
# SEMANTIC MATCHING LAYER  (optional utility — not part of the main pipeline)
# =============================================================================

_encoder = None


def _get_encoder():
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
            _encoder = False
    return _encoder if _encoder is not False else None


def _cosine_similarity_matrix(a, b):
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
    Returns [{ "resume_skill", "target_skill", "score" }, ...] sorted by score.
    Falls back to substring matching if sentence-transformers is not installed.
    """
    if not resume_skills or not target_skills:
        return []

    encoder = _get_encoder()

    if encoder is None:
        matches = []
        for rs in resume_skills:
            for ts in target_skills:
                if rs.lower() in ts.lower() or ts.lower() in rs.lower():
                    matches.append({"resume_skill": rs, "target_skill": ts, "score": 1.0})
        return matches

    src_emb    = encoder.encode(resume_skills, convert_to_numpy=True, show_progress_bar=False)
    tgt_emb    = encoder.encode(target_skills, convert_to_numpy=True, show_progress_bar=False)
    sim_matrix = _cosine_similarity_matrix(src_emb, tgt_emb)

    matches = []
    for i, rs in enumerate(resume_skills):
        for j, ts in enumerate(target_skills):
            score = float(sim_matrix[i, j])
            if score >= threshold:
                matches.append({"resume_skill": rs, "target_skill": ts, "score": round(score, 3)})

    return sorted(matches, key=lambda x: x["score"], reverse=True)


def find_missing_skills(
    resume_skills: list,
    target_skills: list,
    threshold: float = 0.62,
) -> list:
    """
    Return target skills not covered by any resume skill above the threshold.
    Use this for gap analysis when a job description is available.
    """
    if not target_skills:
        return []
    if not resume_skills:
        return target_skills[:]
    matched = {m["target_skill"] for m in semantic_skill_match(resume_skills, target_skills, threshold)}
    return [ts for ts in target_skills if ts not in matched]


# =============================================================================
# PUBLIC API
# =============================================================================

def extract_resume(sections: dict) -> dict:
    """
    Convert raw sections dict (from pdf_parser.parse_resume) into structured JSON.

    Primary path: Groq LLM (llama-3.3-70b-versatile).
      - Handles any resume format, section naming, or layout.
      - No rules to maintain.

    Fallback path: rule-based parsing.
      - Activates automatically on API failure, quota error, or invalid JSON.
      - Covers well-formatted resumes reliably.

    Args:
        sections: Output of pdf_parser.parse_resume()

    Returns:
        {
            "skills":     [str, ...],
            "experience": [{"company", "role", "duration", "bullets"}, ...],
            "education":  [{"degree", "institution", "grade", "year"}, ...],
            "projects":   [{"title", "duration", "bullets"}, ...]
        }
    """
    prompt = _build_extraction_prompt(sections)
    if not prompt:
        print("[resume_extraction] No content to extract — returning empty result.")
        return _empty_result()

    print("[resume_extraction] Calling Groq for structured extraction...")
    try:
        response = _CLIENT.chat.completions.create(
            model=_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise resume parser. "
                        "Extract structured data exactly as instructed and return valid JSON only. "
                        "Never invent or hallucinate data not present in the resume."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw)
        raw = re.sub(r'\s*```$',          '', raw)

        data   = json.loads(raw)
        result = _validate_and_clean(data)

        print(
            f"[resume_extraction] Extracted — "
            f"skills: {len(result['skills'])}, "
            f"experience: {len(result['experience'])}, "
            f"education: {len(result['education'])}, "
            f"projects: {len(result['projects'])}"
        )
        return result

    except Exception as e:
        print(f"[resume_extraction] LLM extraction failed ({e}). Falling back to rule-based...")
        result = _extract_resume_rule_based(sections)
        print(
            f"[resume_extraction] Fallback — "
            f"skills: {len(result['skills'])}, "
            f"experience: {len(result['experience'])}, "
            f"education: {len(result['education'])}, "
            f"projects: {len(result['projects'])}"
        )
        return result

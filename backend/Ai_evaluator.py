# =============================================================================
# ai_evaluator.py
# =============================================================================
# PURPOSE  : Step 3 — Evaluate structured resume data using Gemini 1.5 Flash.
#            Acts as a recruiter: scores the resume, detects weak bullets,
#            rewrites them, and identifies missing skills.
#
# PIPELINE : extract_resume() output → evaluate_resume() → evaluation JSON
#
# INPUT    : {
#               "skills":     [str, ...],
#               "experience": [{"company", "role", "duration", "bullets"}, ...],
#               "education":  [{"degree", "institution", "grade", "year"}, ...],
#               "projects":   [{"title", "duration", "bullets"}, ...]
#            }
#
# OUTPUT   : {
#               "score":          int (0-100, computed in Python),
#               "section_scores": {"bullet_strength", "skill_coverage",
#                                  "project_impact", "education", "completeness"},
#               "reasoning":      [str, ...],
#               "weak_points":    [{"original": str, "improved": str}, ...],
#               "missing_skills": [str, ...]
#            }
#
# REQUIRES : pip install google-generativeai python-dotenv
# API KEY  : Set GEMINI_API_KEY in a .env file in the project root.
# =============================================================================

import os
import json
import re
from dotenv import load_dotenv
from groq import Groq

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

_MODEL  = "llama-3.3-70b-versatile"
_CLIENT = Groq(api_key=os.getenv("GROQ_API_KEY"))


# =============================================================================
# STEP 1 — FORMAT STRUCTURED DATA INTO READABLE PROMPT INPUT
# =============================================================================

def _format_for_prompt(data: dict) -> str:
    """
    Convert extract_resume() output into a recruiter-readable text block.
    The LLM evaluates this text, not raw JSON — it reads closer to an actual resume.
    """
    lines = []

    # Skills
    skills = data.get("skills", [])
    if skills:
        lines.append("SKILLS:")
        lines.append(", ".join(skills))
        lines.append("")

    # Experience
    experience = data.get("experience", [])
    if experience:
        lines.append("EXPERIENCE:")
        for i, exp in enumerate(experience, 1):
            company  = exp.get("company", "")
            role     = exp.get("role", "")
            duration = exp.get("duration", "")
            bullets  = exp.get("bullets", [])
            header   = " | ".join(filter(None, [company, role, duration]))
            lines.append(f"[{i}] {header}")
            for b in bullets:
                lines.append(f"    - {b}")
        lines.append("")

    # Projects
    projects = data.get("projects", [])
    if projects:
        lines.append("PROJECTS:")
        for i, proj in enumerate(projects, 1):
            title    = proj.get("title", "")
            duration = proj.get("duration", "")
            bullets  = proj.get("bullets", [])
            header   = " | ".join(filter(None, [title, duration]))
            lines.append(f"[{i}] {header}")
            for b in bullets:
                lines.append(f"    - {b}")
        lines.append("")

    # Education
    education = data.get("education", [])
    if education:
        lines.append("EDUCATION:")
        for edu in education:
            degree      = edu.get("degree", "")
            institution = edu.get("institution", "")
            grade       = edu.get("grade", "")
            year        = edu.get("year", "")
            parts = [degree, institution]
            if grade:
                parts.append(f"CGPA/Score: {grade}")
            if year:
                parts.append(f"Year: {year}")
            lines.append(" | ".join(filter(None, parts)))

    return "\n".join(lines)


# =============================================================================
# STEP 2 — BUILD THE PROMPT
# =============================================================================

def _build_prompt(formatted_resume: str, job_description: str = None) -> str:
    """
    Build the full prompt sent to Gemini.
    Instructs the LLM to act as a recruiter and return structured JSON only.
    """
    jd_block = ""
    if job_description and job_description.strip():
        jd_block = f"""
JOB DESCRIPTION:
{job_description.strip()}

Use the job description to identify missing skills. Compare the candidate's skills against what the JD requires.
"""
    else:
        jd_block = """
No job description provided. For missing_skills, suggest common industry skills that someone with this candidate's profile (based on their domain, tools, and experience level) would be expected to have but is currently lacking.
"""

    prompt = f"""You are an experienced technical recruiter evaluating a candidate's resume.

Evaluate the following resume and return a JSON object only — no explanation, no markdown, no code fences.

{jd_block}

RESUME:
{formatted_resume}

---

SCORING INSTRUCTIONS:

Score each section independently. Be honest — do not inflate scores.

1. bullet_strength (0-30):
   - Award points for: strong action verbs (Engineered, Designed, Built), quantified results (200+ users, 40% improvement), clear impact
   - Deduct for: vague verbs (worked on, helped, assisted), no numbers, bullets under 8 words
   - Note: some text may appear concatenated (words joined) — read it as compressed text and evaluate the meaning

2. skill_coverage (0-25):
   - Award points for: breadth of skills across multiple domains, relevance to their experience level, no contradictions between skills and experience

3. project_impact (0-25):
   - Award points for: real-world projects (not just tutorials), production deployment, technical depth, use of modern tools

4. education (0-10):
   - Award points for: relevant degree, strong CGPA (8+ out of 10), reputed institution

5. completeness (0-10):
   - Award points for: all sections present, consistent timeline, no obvious gaps

---

WEAK BULLET DETECTION:

Find up to 3 bullets that are vague, passive, or lack impact.
For each, provide an improved version that:
- Starts with a strong action verb
- Adds a measurable result if possible
- Stays truthful to what the candidate described

---

MISSING SKILLS:

List 3-5 skills that are absent from the resume but highly expected for someone at this candidate's level and domain.

---

Return ONLY this JSON (no extra text):

{{
  "section_scores": {{
    "bullet_strength": <int 0-30>,
    "skill_coverage": <int 0-25>,
    "project_impact": <int 0-25>,
    "education": <int 0-10>,
    "completeness": <int 0-10>
  }},
  "reasoning": [
    "<observation 1>",
    "<observation 2>",
    "<observation 3>"
  ],
  "weak_points": [
    {{
      "original": "<exact bullet text>",
      "improved": "<rewritten bullet>"
    }}
  ],
  "missing_skills": ["<skill1>", "<skill2>", "<skill3>"]
}}"""

    return prompt


# =============================================================================
# STEP 3 — CALL GEMINI AND PARSE RESPONSE
# =============================================================================

def _call_gemini(prompt: str) -> dict:
    """
    Send prompt to Gemini 1.5 Flash and parse the JSON response.
    Returns the parsed dict or raises ValueError on failure.
    """
    response = _CLIENT.models.generate_content(model=_MODEL, contents=prompt)
    raw      = response.text.strip()

    # Strip markdown code fences if Gemini adds them despite instructions
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"[ai_evaluator] Gemini returned invalid JSON: {e}\nRaw: {raw[:300]}")


# =============================================================================
# STEP 4 — COMPUTE FINAL SCORE IN PYTHON (not by LLM)
# =============================================================================

def _compute_score(section_scores: dict) -> int:
    """
    Sum section scores into a final 0-100 score.
    Done in Python — not by the LLM — for consistency and reproducibility.
    Clamps each section to its maximum to guard against LLM over-scoring.
    """
    maxes = {
        "bullet_strength": 30,
        "skill_coverage":  25,
        "project_impact":  25,
        "education":       10,
        "completeness":    10,
    }
    total = 0
    for key, cap in maxes.items():
        raw_val = section_scores.get(key, 0)
        total  += min(int(float(raw_val)), cap)

    return min(total, 100)


# =============================================================================
# STEP 5 — VALIDATE RESPONSE SHAPE
# =============================================================================

def _validate(result: dict) -> dict:
    """
    Ensure the LLM response has all required keys.
    Fills in defaults for any missing fields so downstream never breaks.
    """
    result.setdefault("section_scores", {})
    result.setdefault("reasoning",      ["No reasoning provided."])
    result.setdefault("weak_points",    [])
    result.setdefault("missing_skills", [])

    # Ensure weak_points have both keys
    cleaned = []
    for wp in result["weak_points"]:
        if isinstance(wp, dict) and "original" in wp and "improved" in wp:
            cleaned.append(wp)
    result["weak_points"] = cleaned

    return result


# =============================================================================
# PUBLIC API
# =============================================================================

def evaluate_resume(data: dict, job_description: str = None) -> dict:
    """
    Evaluate a structured resume dict using Gemini 1.5 Flash.

    Args:
        data:            Output of resume_extraction.extract_resume()
        job_description: Optional job description text for gap analysis.
                         If None, the LLM suggests commonly expected skills instead.

    Returns:
        {
            "score":          int,        # 0-100, Python-computed sum
            "section_scores": dict,       # per-dimension breakdown
            "reasoning":      [str],      # 3-5 recruiter observations
            "weak_points":    [{"original": str, "improved": str}],
            "missing_skills": [str]
        }

    Usage:
        from pdf_parser import parse_resume
        from resume_extraction import extract_resume
        from ai_evaluator import evaluate_resume

        sections  = parse_resume("resume.pdf")
        data      = extract_resume(sections)
        result    = evaluate_resume(data)
        print(result["score"])
    """
    print("[ai_evaluator] Formatting resume for prompt...")
    formatted = _format_for_prompt(data)

    print("[ai_evaluator] Building prompt...")
    prompt = _build_prompt(formatted, job_description)

    print(f"[ai_evaluator] Calling {_MODEL}...")
    raw_result = _call_gemini(prompt)

    print("[ai_evaluator] Validating response...")
    raw_result = _validate(raw_result)

    print("[ai_evaluator] Computing final score...")
    score = _compute_score(raw_result["section_scores"])

    return {
        "score":          score,
        "section_scores": raw_result["section_scores"],
        "reasoning":      raw_result["reasoning"],
        "weak_points":    raw_result["weak_points"],
        "missing_skills": raw_result["missing_skills"],
    }


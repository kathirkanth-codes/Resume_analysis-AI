# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the server

```bash
uvicorn main:app --reload
```

## Running pipeline tests (CLI, no server needed)

```bash
# Full pipeline: parse → extract → evaluate
python test_evaluator.py

# Parser + extraction only
python test_extraction.py

# PDF parser only
python test_parser.py
```

## Required environment

Create a `.env` file in the project root with:

```
GROQ_API_KEY=your_key_here
```

Both `resume_extraction.py` and `Ai_evaluator.py` load this at module import time via `python-dotenv`.

## Architecture

The project is a FastAPI backend that analyzes resume PDFs through a four-step pipeline. Each step is a separate module with a single public function.

```
POST /analyze (PDF upload)
    │
    ├─ pdf_parser.parse_resume(path)         → sections dict
    ├─ resume_extraction.extract_resume(sections) → structured dict
    ├─ Ai_evaluator.evaluate_resume(structured)  → evaluation dict
    └─ resume_roast.roast_resume(structured)     → roast dict
```

### `pdf_parser.py` — PDF → `{section_name: text}`

Extracts raw text from PDFs using `pdfplumber`, handling two-column layouts. It auto-detects where the two-column zone starts (`_detect_two_col_start_y`), splits the page into Zone A (full-width header) and Zone B (left/right columns), and preserves ATS reading order. Uses character-level word reconstruction (`_chars_to_word_dicts`) instead of `extract_words` to fix word-merging on compressed-font PDFs. Outputs a dict keyed by canonical section names (e.g. `"SKILLS"`, `"EXPERIENCE"`, `"HEADER"`). Aliases (e.g. `"CORE COMPETENCIES"` → `"SKILLS"`) are defined in `HEADER_ALIASES`.

### `resume_extraction.py` — sections dict → structured JSON

Primary path: Groq LLM (`llama-3.3-70b-versatile`) extracts structured data from the section text. Fallback path: rule-based parsing activates automatically on any API failure. Output shape is always `{ skills: [], experience: [], education: [], projects: [] }`. Also exposes `semantic_skill_match()` and `find_missing_skills()` as optional utilities (requires `sentence-transformers`).

### `Ai_evaluator.py` — structured dict → evaluation JSON

Uses Groq (also `llama-3.3-70b-versatile`, named "Gemini" in comments — ignore the naming inconsistency). The LLM scores five dimensions (bullet_strength/30, skill_coverage/25, project_impact/25, education/10, completeness/10). The final `score` (0–100) is computed in Python by summing clamped section scores — never by the LLM. Returns `{ score, section_scores, reasoning, weak_points, missing_skills }`.

### `resume_roast.py` — structured dict → roast JSON

Uses Groq `llama3-8b-8192` (smaller/faster model). Returns `{ roast: [{target, hot_take}], verdict, one_liner }`.

## LLM model usage

| Module | Model | Purpose |
|---|---|---|
| `resume_extraction.py` | `llama-3.3-70b-versatile` | Structured extraction |
| `Ai_evaluator.py` | `llama-3.3-70b-versatile` | Resume scoring |
| `resume_roast.py` | `llama3-8b-8192` | Roast generation |

All LLM calls go through the Groq client. `Ai_evaluator.py` mistakenly uses `_CLIENT.models.generate_content()` (Gemini-style API) — this will fail at runtime; the correct Groq call is `_CLIENT.chat.completions.create()` as used in the other modules.

## Pipeline data contracts

`parse_resume` → `extract_resume`: `dict[str, str]` where keys are uppercase section names.

`extract_resume` → `evaluate_resume` / `roast_resume`:
```json
{
  "skills": ["str"],
  "experience": [{"company": "", "role": "", "duration": "", "bullets": []}],
  "education": [{"degree": "", "institution": "", "grade": "", "year": ""}],
  "projects": [{"title": "", "duration": "", "bullets": []}]
}
```

`/analyze` response:
```json
{ "evaluation": {...}, "roast": {...} }
```

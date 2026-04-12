SYSTEM PIPELINE DEFINITION

This project follows a strict pipeline. All modules must follow this flow.

-----------------------------------

STEP 1: PDF PARSING (pdf_parser.py)
- Input: Resume PDF
- Output:
  {
    "SKILLS": "...",
    "EXPERIENCE": "...",
    "EDUCATION": "...",
    "PROJECTS": "..."
  }

RULE:
- This module is already implemented
- DO NOT modify this file

-----------------------------------

STEP 2: STRUCTURED EXTRACTION (resume_extraction.py)
- Input: Sections dictionary from pdf_parser
- Output:
  {
    "skills": [],
    "experience": [],
    "education": [],
    "projects": []
  }

RULE:
- Must use rule-based logic only
- NO AI allowed in this step

-----------------------------------

STEP 3: AI EVALUATION (ai_evaluator.py)
- Input: Structured JSON from extraction
- Output:
  {
    "score": 0-100,
    "reasoning": [],
    "weak_points": [],
    "missing_skills": []
  }

RULE:
- AI (LLM) is used ONLY here
- Must generate meaningful and structured outputs

-----------------------------------

STEP 4: BACKEND (FastAPI)
- Handles:
  - file upload
  - calling parser → extraction → evaluator
  - returning final JSON

-----------------------------------

STEP 5: FRONTEND (React)
- Upload resume
- Display results
- No processing logic

-----------------------------------

IMPORTANT CONSTRAINTS:
- DO NOT merge steps
- DO NOT use AI in parsing or extraction
- DO NOT redesign pipeline
- Each module must strictly follow input/output contracts

-----------------------------------

FUTURE EXTENSION (NOT IMPLEMENTED):
- Vector database for resume comparison
- Will be added after core system is stable
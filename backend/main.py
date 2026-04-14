import os
import sys
import shutil
import tempfile

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

from pdf_parser import parse_resume
from resume_extraction import extract_resume
from Ai_evaluator import evaluate_resume
from resume_roast import roast_resume

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check():
    return {"status": "running"}


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    job_description: Optional[str] = Form(default=None),
):

    # Only accept PDFs
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Save uploaded file temporarily (unique name avoids concurrent-upload collisions)
    fd, temp_path = tempfile.mkstemp(suffix=".pdf")
    with os.fdopen(fd, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # Step 1 — Parse PDF
        sections = parse_resume(temp_path)
        if not sections:
            raise HTTPException(status_code=422, detail="Could not parse resume. Check the PDF.")

        # Step 2 — Extract structured data
        structured = extract_resume(sections)

        # Step 3 — AI Evaluation
        evaluation = evaluate_resume(structured, job_description=job_description)

        # Step 3.5 — Resume Roast
        roast = roast_resume(structured, job_description=job_description)

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Always delete temp file even if something crashes
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return {
        "evaluation": evaluation,
        "roast": roast
    }

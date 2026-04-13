import os
import json
import re
from dotenv import load_dotenv
from groq import Groq

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """
You are a senior tech recruiter with 15 years of experience. 
You have seen 50,000 resumes. You are honest, direct, and slightly brutal — 
but always fair and always specific.

Your job is to roast this resume.

NOT a generic critique. You read the actual content and react to it.
You call out vague language, missing numbers, weak project descriptions, 
buzzword stacking, and anything that would make a recruiter skip the resume.

You also acknowledge when something is genuinely strong.

Rules:
- Be specific. Quote or reference actual lines from the resume.
- Be punchy. One reaction per item, max 2 sentences.
- Do not be cruel. Be the honest mentor nobody paid for.
- Do not repeat the same critique twice.
- Sound like a human, not a checklist.
"""


def _build_user_prompt(structured_data: dict) -> str:
    skills = ", ".join(structured_data.get("skills", []))

    experience_lines = []
    for job in structured_data.get("experience", []):
        role = job.get("role", "Unknown Role")
        company = job.get("company", "Unknown Company")
        duration = job.get("duration", "")
        bullets = " | ".join(job.get("bullets", []))
        experience_lines.append(f"{role} at {company} ({duration}): {bullets}")
    experience_block = "\n".join(experience_lines) if experience_lines else "No experience listed."

    project_lines = []
    for project in structured_data.get("projects", []):
        name = project.get("title", "Unnamed Project")
        bullets = " | ".join(project.get("bullets", []))
        project_lines.append(f"{name}: {bullets}")
    projects_block = "\n".join(project_lines) if project_lines else "No projects listed."

    education_lines = []
    for edu in structured_data.get("education", []):
        degree = edu.get("degree", "")
        institution = edu.get("institution", "")
        grade = edu.get("grade", "")
        education_lines.append(f"{degree} at {institution}, Grade: {grade}")
    education_block = "\n".join(education_lines) if education_lines else "No education listed."

    return f"""Here is the candidate's resume data:

SKILLS: {skills}

EXPERIENCE:
{experience_block}

PROJECTS:
{projects_block}

EDUCATION:
{education_block}

Now roast this resume.

Return ONLY a valid JSON object with this exact structure — no explanation, no markdown:
{{
  "roast": [
    {{ "target": "...", "hot_take": "..." }},
    {{ "target": "...", "hot_take": "..." }},
    {{ "target": "...", "hot_take": "..." }},
    {{ "target": "...", "hot_take": "..." }}
  ],
  "verdict": "...",
  "one_liner": "..."
}}"""


def roast_resume(structured_data: dict) -> dict:
    user_prompt = _build_user_prompt(structured_data)

    response = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    raw = re.sub(r'^```(?:json)?\s*', '', raw)
    raw = re.sub(r'\s*```$', '', raw)
    raw = raw.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\n\nRaw response:\n{raw}")

    return result
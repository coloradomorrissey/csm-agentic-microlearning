from typing import Optional
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os, sys, traceback
from openai import OpenAI

# --- RUNTIME CONFIG ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
app = FastAPI(title="CSM Microlearning Service", version="0.1")

# Resolve project paths robustly (works no matter where you run uvicorn)
BASE_DIR = Path(__file__).resolve().parent           # .../langchain
PROMPTS_DIR = BASE_DIR.parent / "prompts"            # .../prompts
LESSON_RUBRIC_PATH = PROMPTS_DIR / "lesson" / "lesson_rubric.md"
COACH_PROMPT_PATH   = PROMPTS_DIR / "coach" / "socratic_coach_system.md"

# --- REQUEST MODELS ---
class LessonRequest(BaseModel):
    stage: str
    confidence: int
    last_quiz: int
    scenario_prompt: str

class CoachRequest(BaseModel):
    stage: Optional[str] = None
    confidence: Optional[int] = None
    last_quiz: Optional[int] = None
    scenario_prompt: str

# --- UTILS ---
def load_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing prompt file: {path}")
    return path.read_text(encoding="utf-8")

def call_openai_chat(system_prompt: str, user_prompt: str, model: str = "gpt-4o-mini") -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",    "content": user_prompt},
        ],
        temperature=0.5,
    )
    return resp.choices[0].message.content

# --- ENDPOINTS ---
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/generate_lesson")
def generate_lesson(req: LessonRequest):
    """
    Reads the lesson rubric from disk, injects user context, returns lesson markdown.
    Returns JSON with {"ok": false, "error": "..."} if something fails (auth, file, model).
    """
    try:
        rubric = load_text(LESSON_RUBRIC_PATH)
        user_prompt = f"""
Inputs:
- stage: {req.stage}
- learner_confidence: {req.confidence}
- recent_quiz_score: {req.last_quiz}
- scenario_prompt: {req.scenario_prompt}

Follow the rubric exactly and return markdown only.
""".strip()
        lesson_md = call_openai_chat(rubric, user_prompt, model="gpt-4o-mini")
        return JSONResponse({"ok": True, "lesson_markdown": lesson_md})
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return JSONResponse({"ok": False, "error": str(e)})

@app.post("/coach")
def coach(req: CoachRequest):
    """
    Reads the coach system prompt and returns structured text.
    Returns JSON with {"ok": false, "error": "..."} on failure.
    """
    try:
        system_p = load_text(COACH_PROMPT_PATH)
        user_p = f"""
Learner context:
- stage: {req.stage}
- self_confidence: {req.confidence}
- last_quiz_score: {req.last_quiz}
- scenario: {req.scenario_prompt}

Return the following sections (plain text, labeled):
- coach_message:
- recommended_lesson_stage:
- reasoning_summary:
""".strip()
        coach_text = call_openai_chat(system_p, user_p, model="gpt-4o-mini")
        return JSONResponse({"ok": True, "coach_response": coach_text})
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return JSONResponse({"ok": False, "error": str(e)})

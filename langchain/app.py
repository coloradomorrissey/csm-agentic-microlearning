from fastapi import FastAPI
from pydantic import BaseModel
import os
from openai import OpenAI

# --- RUNTIME CONFIG ---
# Expect an environment variable OPENAI_API_KEY to be set.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI(title="CSM Microlearning Service", version="0.1")

# --- REQUEST MODELS ---
class LessonRequest(BaseModel):
    stage: str               # onboarding | adoption | value_expansion | risk | renewal
    confidence: int          # 1..5
    last_quiz: int           # 0..100
    scenario_prompt: str     # learner's free-text situation

class CoachRequest(BaseModel):
    stage: str | None = None
    confidence: int | None = None
    last_quiz: int | None = None
    scenario_prompt: str

# --- UTILS ---
def load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def call_openai_chat(system_prompt: str, user_prompt: str) -> str:
    """
    Wraps a single chat completion call. Keep temperature moderate for consistency.
    """
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
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
    """
    rubric = load_text("../prompts/lesson/lesson_rubric.md")
    user_prompt = f"""
Inputs:
- stage: {req.stage}
- learner_confidence: {req.confidence}
- recent_quiz_score: {req.last_quiz}
- scenario_prompt: {req.scenario_prompt}

Follow the rubric exactly.
"""
    lesson_md = call_openai_chat(rubric, user_prompt)
    return {"lesson_markdown": lesson_md}

@app.post("/coach")
def coach(req: CoachRequest):
    """
    Reads the coach system prompt and returns a structured response text.
    You can parse this on the Base44 side into UI pieces.
    """
    system_p = load_text("../prompts/coach/socratic_coach_system.md")
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
"""
    coach_text = call_openai_chat(system_p, user_p)
    return {"coach_response": coach_text}

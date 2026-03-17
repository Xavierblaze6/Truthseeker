"""
TruthSeeker – FastAPI entry point
Endpoints:
  POST /fact-check  — run the fact-checking pipeline
  POST /chat        — conversational follow-up using session memory
  GET  /health      — liveness probe
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.models import (
    FactCheckRequest,
    FactCheckResponse,
    ChatRequest,
    ChatResponse,
)
from backend.agents.fact_checker import run_fact_check
from backend.memory import get_history, add_to_history

load_dotenv()

app = FastAPI(title="TruthSeeker", version="1.0.0")

# ── CORS – allow all origins so the static frontend can call the API ──────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend static files
app.mount("/static", StaticFiles(directory="frontend"), name="static")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def serve_frontend():
    """Serve the frontend app entrypoint."""
    return FileResponse("frontend/index.html")

@app.get("/health")
async def health():
    """Liveness probe used by Render and monitoring tools."""
    return {"status": "ok"}


@app.post("/fact-check", response_model=FactCheckResponse)
async def fact_check(req: FactCheckRequest):
    """
    Main fact-checking endpoint.
    Searches Wikipedia, DuckDuckGo and Reddit in parallel,
    then asks GPT-4o-mini to synthesise a verdict.
    """
    try:
        result = await run_fact_check(req.claim)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Persist result in session memory for follow-up chats
    add_to_history(
        session_id=req.session_id,
        role="assistant",
        content=result.model_dump_json(),
    )
    return result


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Conversational follow-up endpoint.
    Uses session history so the model can answer questions like
    "tell me more about that" in context.
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    history = get_history(req.session_id)

    messages = [
        {
            "role": "system",
            "content": (
                "You are TruthSeeker, an expert fact-checking AI assistant. "
                "Answer follow-up questions based on the fact-check results in the conversation history. "
                "Be concise and cite the sources already gathered when relevant."
            ),
        },
        *history,
        {"role": "user", "content": req.message},
    ]

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.3,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    reply = response.choices[0].message.content or ""

    # Keep memory up-to-date
    add_to_history(req.session_id, "user", req.message)
    add_to_history(req.session_id, "assistant", reply)

    return ChatResponse(reply=reply)

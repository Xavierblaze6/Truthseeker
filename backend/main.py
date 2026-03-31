"""
TruthSeeker – FastAPI entry point
Endpoints:
  POST /fact-check  — run the fact-checking pipeline
  POST /chat        — conversational follow-up using session memory
  GET  /health      — liveness probe
"""

import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.models import (
    FactCheckRequest,
    FactCheckResponse,
    ChatRequest,
    ChatResponse,
)
from backend.agents.fact_checker import run_fact_check, is_valid_claim
from backend.agents.image_detector import detect_deepfake
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
    is_valid, error_message = is_valid_claim(req.claim)
    if not is_valid:
        return FactCheckResponse(
            verdict="INVALID",
            credibility_score=0,
            reasoning=error_message,
            supporting_sources=[],
            contradicting_sources=[],
            wikipedia_snippet="",
            web_snippets="",
            reddit_snippets="",
        )

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


@app.post("/detect-image")
async def detect_image(file: UploadFile = File(...)):
    """Detect whether an uploaded image is likely AI-generated/manipulated."""
    allowed_types = {"image/jpeg", "image/png", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image format. Please upload JPG, PNG, or WEBP.",
        )

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, detect_deepfake, image_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Image detection failed. Please try again in a moment.",
        ) from exc

    return result


if __name__ == "__main__":
    import uvicorn
    import os

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

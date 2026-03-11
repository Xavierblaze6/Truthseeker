"""
Pydantic models – request and response shapes used by the FastAPI endpoints.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Requests ──────────────────────────────────────────────────────────────────

class FactCheckRequest(BaseModel):
    claim: str = Field(..., description="The statement / claim to be fact-checked.")
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Client-generated UUID used to track session memory.",
    )


class ChatRequest(BaseModel):
    message: str = Field(..., description="Follow-up question from the user.")
    session_id: str = Field(..., description="Same UUID used in the fact-check request.")


# ── Responses ─────────────────────────────────────────────────────────────────

class FactCheckResponse(BaseModel):
    verdict: str = Field(..., description="TRUE | FALSE | MISLEADING | UNVERIFIED")
    credibility_score: int = Field(..., ge=0, le=100, description="0-100 credibility score.")
    reasoning: str = Field(..., description="2-3 sentence explanation.")
    supporting_sources: List[str] = Field(default_factory=list)
    contradicting_sources: List[str] = Field(default_factory=list)
    # Raw snippets from each source – surfaced in the UI
    wikipedia_snippet: Optional[str] = None
    web_snippets: Optional[str] = None
    reddit_snippets: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str

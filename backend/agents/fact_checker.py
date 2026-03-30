"""
Main orchestrator for TruthSeeker.

Flow:
  1. Accept the user claim.
  2. Search all three sources *in parallel* with asyncio.gather().
  3. Combine evidence into a single context string.
  4. Ask GPT-4o-mini to produce a structured verdict.
  5. Parse and return the FactCheckResponse.
"""

from __future__ import annotations

import asyncio
import json
import os

from openai import AsyncOpenAI

from backend.models import FactCheckResponse
from backend.agents.wikipedia import search_wikipedia
from backend.agents.web_search import search_web
from backend.agents.reddit import search_reddit

# System prompt injected into every GPT-4o-mini call
_SYSTEM_PROMPT = """You are TruthSeeker, an expert fact-checking AI.
Analyze the provided evidence carefully and:
1. Give a verdict: TRUE, FALSE, MISLEADING, or UNVERIFIED
   - TRUE: claim is factually accurate and well supported
   - FALSE: claim is factually incorrect and contradicted by evidence
   - MISLEADING: claim has some truth but is missing context or exaggerated
   - UNVERIFIED: insufficient evidence to confirm or deny
   CRITICAL: If your reasoning describes the claim as a myth, debunked, incorrect, or not supported by evidence, you MUST use FALSE or MISLEADING — never TRUE.
2. Provide a credibility score from 0-100
   - 0-30: FALSE claims
   - 31-60: MISLEADING claims
   - 61-80: UNVERIFIED claims
   - 81-100: TRUE claims only
   IMPORTANT: The score MUST match the verdict. A FALSE or MISLEADING claim can NEVER score above 60.
3. Explain your reasoning in 2-3 sentences
4. List which sources supported or contradicted the claim
Respond ONLY in valid JSON format with keys: verdict, credibility_score, reasoning, supporting_sources, contradicting_sources"""


def is_valid_claim(claim: str) -> tuple[bool, str]:
    """Check if input is actually a verifiable claim, not just a word or phrase."""

    # Too short to be a claim
    if len(claim.split()) < 4:
        return (
            False,
            "Please enter a complete claim to fact-check. Example: 'The Great Wall of China is visible from space'",
        )

    # No verb present (basic check)
    claim_lower = claim.lower()
    verb_indicators = [
        "is",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "can",
        "will",
        "does",
        "did",
        "caused",
        "found",
        "discovered",
        "proven",
        "showed",
    ]
    if not any(verb in claim_lower.split() for verb in verb_indicators):
        return (
            False,
            "Please enter a complete sentence with a verb. Example: 'Coffee is bad for your health'",
        )

    return True, ""


async def run_fact_check(claim: str) -> FactCheckResponse:
    """
    Orchestrate the full fact-checking pipeline and return a structured result.

    Args:
        claim: The statement the user wants checked.

    Returns:
        A populated FactCheckResponse.
    """
    # ── Step 1: Gather evidence from all three sources in parallel ────────────
    wiki_task = asyncio.create_task(_safe_search(search_wikipedia, claim, "Wikipedia"))
    web_task = asyncio.create_task(_safe_search(search_web, claim, "Web"))
    reddit_task = asyncio.create_task(_safe_search(search_reddit, claim, "Reddit"))

    wiki_result, web_result, reddit_result = await asyncio.gather(
        wiki_task, web_task, reddit_task
    )

    # ── Step 2: Build a unified evidence context ──────────────────────────────
    context_parts = []
    if wiki_result:
        context_parts.append(f"[Wikipedia]\n{wiki_result}")
    if web_result:
        context_parts.append(f"[Web Search]\n{web_result}")
    if reddit_result:
        context_parts.append(f"[Reddit]\n{reddit_result}")

    if not context_parts:
        # No source returned anything useful – still ask the model to reason
        context = "No external evidence could be retrieved for this claim."
    else:
        context = "\n\n".join(context_parts)

    # ── Step 3: Ask GPT-4o-mini to produce a structured verdict ──────────────
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    user_message = (
        f"Claim to fact-check: \"{claim}\"\n\n"
        f"Evidence gathered:\n{context}"
    )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        temperature=0.2,  # Low temperature for factual, consistent output
        response_format={"type": "json_object"},
    )

    raw_json = response.choices[0].message.content or "{}"

    # ── Step 4: Parse, validate, and return ──────────────────────────────────
    data = json.loads(raw_json)

    # Normalise verdict to uppercase before validation
    data["verdict"] = (data.get("verdict") or "UNVERIFIED").upper()
    data["credibility_score"] = int(data.get("credibility_score", 50))

    # Fix any verdict/score mismatch the model produced
    data = validate_and_fix_response(data)

    return FactCheckResponse(
        verdict=data["verdict"],
        credibility_score=data["credibility_score"],
        reasoning=data.get("reasoning", ""),
        supporting_sources=data.get("supporting_sources", []),
        contradicting_sources=data.get("contradicting_sources", []),
        wikipedia_snippet=wiki_result,
        web_snippets=web_result,
        reddit_snippets=reddit_result,
    )


def validate_and_fix_response(result: dict) -> dict:
    """
    Post-processing guard: ensure the credibility_score is consistent with
    the verdict.  Called immediately after parsing the raw JSON from GPT.

    Rules:
        FALSE      → score capped at 20  (if model returned > 30)
        MISLEADING → score capped at 45  (if model returned > 60)
        UNVERIFIED → score capped at 65  (if model returned > 80)
        TRUE       → score floored at 75 (if model returned < 70)
    """
    verdict = result.get("verdict", "UNVERIFIED")
    score = result.get("credibility_score", 50)

    if verdict == "FALSE" and score > 30:
        result["credibility_score"] = min(score, 20)
    elif verdict == "MISLEADING" and score > 60:
        result["credibility_score"] = min(score, 45)
    elif verdict == "UNVERIFIED" and score > 80:
        result["credibility_score"] = min(score, 65)
    elif verdict == "TRUE" and score < 70:
        result["credibility_score"] = max(score, 75)

    return result


async def _safe_search(fn, claim: str, source_name: str) -> str:
    """
    Wrapper that runs a (potentially synchronous) search function in a thread
    and swallows exceptions so one failing source does not abort the pipeline.
    """
    try:
        # All source functions are synchronous; run them in the default thread-pool
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, fn, claim)
        return result or ""
    except Exception as exc:  # pylint: disable=broad-except
        # Graceful degradation: log and continue without this source
        print(f"[TruthSeeker] {source_name} search failed: {exc}")
        return ""

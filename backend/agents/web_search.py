"""
Web search agent – powered by DuckDuckGo (no API key required).

Uses the `ddgs` library (formerly duckduckgo-search) to retrieve the top 3
organic results for the claim and formats them as a readable evidence string.
"""

from __future__ import annotations

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS  # fallback for older installs


def search_web(claim: str) -> str:
    """
    Run a DuckDuckGo search for the claim and return the top 3 results.

    Args:
        claim: The user's claim text.

    Returns:
        A formatted multi-line string with title + snippet for each result,
        or an empty string if the search returns nothing.
    """
    results = []

    # DDGS is a context manager; `text()` yields result dicts
    with DDGS() as ddgs:
        for hit in ddgs.text(query=claim, max_results=3):
            title = hit.get("title", "No title")
            body = hit.get("body", "")
            url = hit.get("href", "")
            # Truncate snippets to keep context concise
            snippet = body[:300] if body else "(no snippet)"
            results.append(f"• {title}\n  {snippet}\n  Source: {url}")

    if not results:
        return ""

    return "\n\n".join(results)

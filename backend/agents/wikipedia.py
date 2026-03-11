"""
Wikipedia source agent.

Uses the Wikipedia REST v1 summary endpoint – no API key required.
Returns the first 500 characters of the page summary for the best-matching
article found for the given search term.
"""

from __future__ import annotations

import urllib.parse

import requests

_BASE_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/"
_HEADERS = {"User-Agent": "TruthSeeker/1.0 (fact-checking research tool)"}
_MAX_CHARS = 500


def search_wikipedia(claim: str) -> str:
    """
    Search Wikipedia for the claim and return a short summary snippet.

    Args:
        claim: The user's claim text.

    Returns:
        A text snippet (≤500 chars) from the best-matching Wikipedia article,
        or an empty string if nothing useful is found.
    """
    # Use the first 5 words of the claim as the search term to maximise
    # the chance of hitting a relevant article title.
    search_term = _extract_search_term(claim)
    encoded = urllib.parse.quote(search_term, safe="")
    url = f"{_BASE_URL}{encoded}"

    try:
        resp = requests.get(url, headers=_HEADERS, timeout=5)
    except requests.RequestException as exc:
        raise RuntimeError(f"Wikipedia HTTP request failed: {exc}") from exc

    if resp.status_code == 404:
        # Try again with a shorter term (first 3 words)
        shorter_term = " ".join(claim.split()[:3])
        encoded2 = urllib.parse.quote(shorter_term, safe="")
        try:
            resp = requests.get(f"{_BASE_URL}{encoded2}", headers=_HEADERS, timeout=5)
        except requests.RequestException:
            return ""

    if resp.status_code != 200:
        return ""

    data = resp.json()
    extract: str = data.get("extract", "")

    if not extract:
        return ""

    snippet = extract[:_MAX_CHARS]
    title = data.get("title", "Unknown article")
    return f"{title}: {snippet}"


def _extract_search_term(claim: str) -> str:
    """
    Convert a claim sentence to a concise Wikipedia search term by taking
    the first 5 words and title-casing them.
    """
    words = claim.strip().split()
    term = " ".join(words[:5])
    return term.title()

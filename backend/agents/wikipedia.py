"""Wikipedia source agent using search + summary API flow."""

from __future__ import annotations

import requests

_SEARCH_URL = "https://en.wikipedia.org/w/api.php"
_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{}"
_HEADERS = {"User-Agent": "TruthSeeker/1.0 (fact-checking tool)"}
_MAX_CHARS = 600


def search_wikipedia(claim: str) -> str:
    """Search Wikipedia for claim context and return a short summary snippet."""
    try:
        search_params = {
            "action": "query",
            "list": "search",
            "srsearch": claim,
            "format": "json",
            "srlimit": 1,
        }
        search_response = requests.get(
            _SEARCH_URL,
            params=search_params,
            headers=_HEADERS,
            timeout=10,
        )
        search_response.raise_for_status()
        search_data = search_response.json()

        if not search_data.get("query", {}).get("search"):
            return "No Wikipedia results found."

        top_title = search_data["query"]["search"][0]["title"]
        summary_response = requests.get(
            _SUMMARY_URL.format(top_title.replace(" ", "_")),
            headers=_HEADERS,
            timeout=10,
        )

        if summary_response.status_code == 200:
            data = summary_response.json()
            extract = data.get("extract", "No summary available.")
            return extract[:_MAX_CHARS]

        return "No Wikipedia results found."
    except Exception as exc:  # pylint: disable=broad-except
        return f"Wikipedia search failed: {str(exc)}"

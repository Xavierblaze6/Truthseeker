"""Reddit source agent using the public search endpoint."""

from __future__ import annotations

import requests

_SEARCH_URL = "https://www.reddit.com/search.json"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 TruthSeeker/1.0 (fact-checking research tool)"
}


def search_reddit(claim: str) -> str:
    """Search Reddit for discussions related to the claim."""
    try:
        params = {
            "q": claim,
            "limit": 3,
            "sort": "relevance",
            "type": "link",
        }

        response = requests.get(
            _SEARCH_URL,
            params=params,
            headers=_HEADERS,
            timeout=10,
        )

        if response.status_code != 200:
            return "Reddit search temporarily unavailable."

        data = response.json()
        posts = data.get("data", {}).get("children", [])

        if not posts:
            return "No Reddit discussions found."

        results = []
        for post in posts[:3]:
            post_data = post.get("data", {})
            title = post_data.get("title", "")
            score = post_data.get("score", 0)
            subreddit = post_data.get("subreddit", "")
            results.append(f"• [r/{subreddit}] {title} (score: {score})")

        return "\n".join(results)
    except Exception as exc:  # pylint: disable=broad-except
        return f"Reddit search failed: {str(exc)}"

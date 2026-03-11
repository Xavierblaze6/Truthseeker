"""
Reddit source agent.

Uses Reddit's public JSON API (no OAuth required) to find the top 3 posts
related to the claim and returns their titles and scores as evidence text.

Subreddits are chosen dynamically based on the topic of the claim so results
are always relevant (e.g. health claims → r/medicine, space claims → r/space).
"""

from __future__ import annotations

import requests

_SEARCH_URL = "https://www.reddit.com/search.json"
_HEADERS = {"User-Agent": "TruthSeeker/1.0"}

# Keyword → list of relevant subreddits.
# The first matching category wins; the fallback covers everything else.
_TOPIC_SUBREDDITS: list[tuple[list[str], list[str]]] = [
    # Health / medicine / nutrition
    (
        ["health", "medicine", "medical", "drug", "vaccine", "virus", "cancer",
         "disease", "diet", "nutrition", "vitamin", "weight", "calorie", "food",
         "covid", "symptom", "doctor", "hospital", "mental", "sleep"],
        ["medicine", "health", "nutrition", "science", "askscience"],
    ),
    # Space / astronomy / physics
    (
        ["space", "nasa", "planet", "star", "moon", "asteroid", "orbit",
         "galaxy", "universe", "cosmos", "rocket", "astronaut", "mars", "earth",
         "gravity", "physics", "light", "speed"],
        ["space", "astronomy", "physics", "askscience", "science"],
    ),
    # Technology / AI / software
    (
        ["ai", "artificial intelligence", "machine learning", "software",
         "computer", "internet", "tech", "robot", "algorithm", "data",
         "phone", "app", "crypto", "bitcoin", "blockchain", "hack",
         "programming", "python", "javascript", "code", "developer"],
        ["technology", "artificial", "MachineLearning", "compsci", "science"],
    ),
    # History / geography / politics
    (
        ["history", "war", "country", "president", "election", "government",
         "politics", "law", "constitution", "geography", "capital", "nation",
         "ancient", "century", "world", "china", "usa", "europe"],
        ["history", "geography", "worldnews", "PoliticalDiscussion", "askhistorians"],
    ),
    # Economics / finance
    (
        ["economy", "economic", "inflation", "gdp", "stock", "finance",
         "money", "bank", "market", "trade", "tax", "recession"],
        ["economics", "finance", "investing", "worldnews", "science"],
    ),
    # Environment / climate
    (
        ["climate", "environment", "carbon", "emission", "global warming",
         "pollution", "renewable", "energy", "fossil", "ocean", "temperature"],
        ["environment", "climate", "science", "askscience", "worldnews"],
    ),
]

# Fallback subreddits used when no topic matches
_DEFAULT_SUBREDDITS = ["science", "askscience", "worldnews", "truereddit", "explainlikeimfive"]


def _pick_subreddits(claim: str) -> list[str]:
    """Return the most relevant subreddit list for the claim's topic."""
    lower = claim.lower()
    for keywords, subreddits in _TOPIC_SUBREDDITS:
        if any(kw in lower for kw in keywords):
            return subreddits
    return _DEFAULT_SUBREDDITS


def search_reddit(claim: str) -> str:
    """
    Search Reddit for the claim in topic-relevant subreddits and return
    a snippet of the top 3 posts.

    Args:
        claim: The user's claim text.

    Returns:
        A formatted string with post titles and scores, or empty string on failure.
    """
    subreddits = _pick_subreddits(claim)
    subreddit_filter = "+OR+".join(f"subreddit:{s}" for s in subreddits)
    query = f"{claim} {subreddit_filter}"

    params = {
        "q": query,
        "limit": 3,
        "sort": "relevance",
        "type": "link",       # posts only, not comments
    }

    try:
        resp = requests.get(
            _SEARCH_URL,
            params=params,
            headers=_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Reddit API request failed: {exc}") from exc

    data = resp.json()
    posts = data.get("data", {}).get("children", [])

    if not posts:
        return ""

    lines = []
    for post in posts:
        p = post.get("data", {})
        title = p.get("title", "No title")
        score = p.get("score", 0)
        subreddit = p.get("subreddit_name_prefixed", "r/?")
        selftext = p.get("selftext", "")
        # Include a brief excerpt from self-text if available
        excerpt = f" — \"{selftext[:150]}\"" if selftext else ""
        lines.append(f"• [{subreddit}] {title} (score: {score}){excerpt}")

    return "\n".join(lines)

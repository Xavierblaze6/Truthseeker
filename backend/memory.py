"""
Session-based dialogue memory.

Stores the last 5 fact-check / chat turns per session so the conversational
/chat endpoint has context for follow-up questions.

Storage is in-process (plain dict).  For production you would swap this for
Redis or a database, but for a single-server deploy this is perfectly fine.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any, Dict, List

# session_id → deque of {"role": ..., "content": ...} dicts
_store: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10))

_MAX_MESSAGES = 10  # 5 exchanges = 10 messages (user + assistant)


def add_to_history(session_id: str, role: str, content: str) -> None:
    """Append a message to the session history, honouring the rolling window."""
    _store[session_id].append({"role": role, "content": content})


def get_history(session_id: str) -> List[Dict[str, Any]]:
    """Return the full (windowed) history for the given session."""
    return list(_store.get(session_id, []))


def clear_history(session_id: str) -> None:
    """Wipe history for a session (useful for testing)."""
    _store.pop(session_id, None)

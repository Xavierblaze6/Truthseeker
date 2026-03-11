# TruthSeeker – Copilot Instructions

## Project overview
TruthSeeker is a FastAPI + vanilla-JS fact-checking agent.
The backend lives in `backend/`, the static frontend in `frontend/`.

## Code conventions
- Python 3.10+, type hints everywhere, docstrings on every public function.
- All async I/O uses `asyncio`; sync third-party libs are wrapped with `run_in_executor`.
- Error handling: swallow individual source failures gracefully; never crash the pipeline.
- Pydantic v2 models in `backend/models.py`.

## Architecture rules
- Do NOT add authentication — the app is intentionally public-read.
- Source agents (`wikipedia.py`, `web_search.py`, `reddit.py`) must stay synchronous and be called via `run_in_executor` in `fact_checker.py`.
- Session memory (`memory.py`) stores at most 10 messages per session.
- CORS is `allow_origins=["*"]` by design — required for the static frontend.

## Frontend
- No build step; `index.html` opens directly in a browser.
- Chart.js loaded from CDN.
- `API_BASE` in `app.js` defaults to `http://localhost:8000`.

## Running locally
```
uvicorn backend.main:app --reload --port 8000
```
Then open `frontend/index.html` in a browser.

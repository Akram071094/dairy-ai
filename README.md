# dairy-ai

AI services powering Operational Memory, recommendations, forecasting, business insights, and intelligent assistants for Dairy OS.

The deterministic recommendation engine (stock & collections) consumes shared PostgreSQL operational data and exposes a stable `/api/v1/recommendations` contract, ready for an Ollama-powered scoring swap later.

## API

- `GET  /api/v1/health` — liveness probe
- `GET  /api/v1/recommendations` — list recommendation capabilities
- `POST /api/v1/recommendations` — generate recommendations for a domain
- `GET  /api/v1/recommendations/stored/{organization_id}` — precomputed rows from the async job

## Async job

Precompute recommendations into the `ai_recommendations` table so the UI/backend can serve them without running ML logic in the request path:

```bash
python -m scripts.run_recommendation_job                          # all orgs, all domains
python -m scripts.run_recommendation_job --org-id <uuid> --domain stock --top-n 50
```

## Getting started

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
cp .env.example .env      # set DATABASE_URL
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

## Code quality

```bash
ruff check .
ruff format --check .
mypy app/ ml/ scripts/
python -m pytest tests/
```

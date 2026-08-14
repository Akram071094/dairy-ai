# dairy-ai

AI services for Dairy OS — the **governed agentic platform** (per klyra HLD-110) plus the deterministic recommendation engine.

## What this service does

- **Agentic platform**: agent registry, orchestrator, tool registry/executor, deterministic rule-based agents
- **Governance**: policies, human-in-the-loop approvals, audit trail
- **Recommendations**: stock & collections scoring (deterministic today, Ollama later)
- Operates alongside `dairy-backend` (system of record) and `dairy-frontend` (Action Center)

## Architecture

```
dairy-frontend (Action Center)
   ├── GET  /api/v1/agents/available-actions   (dairy-ai)
   ├── POST /api/v1/agent/execute              (dairy-ai)
   └── business reads/writes                    (dairy-backend)

dairy-ai (agent platform)
   ├── reads shared PostgreSQL (read-only operational data)
   └── executes actions via dairy-backend REST APIs (double authorization)

dairy-backend (system of record)
   └── auth/RBAC, business CRUD, operational memory
```

## Getting started

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
cp .env.example .env      # set DATABASE_URL + BACKEND_*
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

## API

- `GET  /api/v1/recommendations` — list capabilities
- `POST /api/v1/recommendations` — generate recommendations
- `GET  /api/v1/recommendations/stored/{organization_id}` — precomputed rows
- `GET  /api/v1/agents/available-actions` — agent-driven actions for the Action Center
- `POST /api/v1/agent/execute` — run an agent workflow
- `GET  /api/v1/agent/executions/{id}` — execution status
- `GET  /api/v1/agent/health` — agent platform health

## Code quality

```bash
ruff check .
ruff format --check .
mypy app/ ml/ scripts/
python -m pytest tests/
```

## Roadmap

- Phase 1 (now): foundation — agent registry, orchestrator, tool execution, JWT integration
- Phase 2: governance — policy engine, approvals, audit trail
- Phase 3: LLM integration — pluggable planner (Ollama)
- Phase 4: advanced orchestration

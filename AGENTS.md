# AI Coding Assistant Instructions

## Overview

This document provides guidelines for AI coding assistants working on the Dairy AI service repository (dairy-ai).

dairy-ai is the **governed agentic platform** for Dairy OS (see `klyra` HLD-110). It provides agentic workflows, sub-agents, tool execution, governance policies, approval workflows, and audit trails, integrating cleanly with dairy-backend. It also hosts the deterministic recommendation engine.

## This Repository Handles

- **Agentic platform**: agent registry, orchestrator, tool registry/executor, deterministic rule-based agents (Ollama/LLM in a later phase)
- **Governance**: policies, approvals (human-in-the-loop), audit trail
- **Recommendation generation** (deterministic engine today, Ollama later)
- Consuming operational data from the **shared PostgreSQL database** (owned by dairy-platform/dairy-backend schema)
- Exposing capabilities as a FastAPI service deployed separately from dairy-backend

## This Repository Does NOT Handle

- Business CRUD APIs (those live in dairy-backend)
- Database schema design, migrations, or RLS of operational tables (owned by dairy-platform)
- Authentication/authorization of end users (dairy-backend owns that; dairy-ai validates forwarded JWTs and reads shared tables)
- Business actions — agents **execute** via dairy-backend REST APIs (double-authorization; backend remains the final authority)

## Critical Rules

### 1. Never Change Operational Schema

```markdown
✅ DO: Consume existing tables (inventory, stock_movements, outstandings, retailers, ...)
✅ DO: Read columns defined by dairy-backend models
✅ DO: Create/manage dairy-ai-owned tables only:
      ai_recommendations, agent_definitions, agent_executions, approval_requests, audit_events
❌ DON'T: Modify column types
❌ DON'T: Add new columns to existing operational tables
❌ DON'T: Create tables outside the dairy-ai-owned list above
```

### 2. Read-Only Data Access on Operational Data

```markdown
✅ DO: Run SELECT queries against the shared PostgreSQL DB (operational tables)
✅ DO: Write only to dairy-ai-owned tables (agent executions, approvals, audit, recommendations)
❌ DON'T: INSERT/UPDATE/DELETE operational data directly — route actions through dairy-backend APIs
```

### 2b. Double Authorization

```markdown
✅ DO: Validate forwarded JWTs and check agent/tool capability requirements
✅ DO: Call dairy-backend via its REST APIs for every business action
✅ DO: Rely on dairy-backend's own permission checks as the final authority
❌ DON'T: Bypass dairy-backend authorization or access the DB for business actions
```

### 3. Keep the API Contract Stable

```markdown
✅ DO: Treat the /api/v1/recommendations contract as the stable interface
✅ DO: Swap the scoring "brain" (deterministic → Ollama) without changing schemas
❌ DON'T: Change request/response schemas arbitrarily
```

### 4. Keep Controllers Thin

```markdown
✅ DO: Endpoints delegate to services
✅ DO: Services call the data/ML layers
✅ DO: Return Pydantic DTOs
❌ DON'T: Write business logic in endpoint handlers
```

### 5. No ML Models Yet

```markdown
✅ DO: Use the deterministic decision engine (ml/engine)
✅ DO: Reserve ml/models for future Ollama artifacts
❌ DON'T: Wire in scikit-learn/training pipelines until the next phase
```

## File Naming Conventions

- Routes: `app/api/<feature>/*.py` (e.g., recommendations.py, health.py, agent.py; registered via `app/api/<feature>/__init__.py`)
- Services: `app/services/*_service.py`
- Schemas: `app/models/schemas.py`
- Agents: `app/agents/*_agent.py` (base.py, registry.py)
- Tools: `app/tools/*.py` (registry.py, executor.py)
- ML engine: `ml/engine/*.py`
- Feature builders: `ml/features/*.py`

## Import Order

```python
# 1. Standard library
import uuid
from datetime import datetime

# 2. Third-party
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

# 3. Local application
from app.models.schemas import RecommendationResponse
from app.agents.registry import agent_registry
from ml.engine.decision_engine import DecisionEngine
```

## Code Quality

```bash
ruff check .
ruff format --check .
mypy app/ ml/ scripts/
python -m pytest tests/
```

## Common Mistakes to Avoid

1. Querying non-existent tables/columns → check `dairy-backend/app/**/models/*.py` for real schema
2. Using the RangeIndex as an ID in pandas iterrows → use the real id column (sku_id, retailer_id)
3. Reading a stray `.env` in tests → build `Settings(_env_file=None)` or pin env in fixtures
4. Adding ML/LLM dependencies → keep requirements minimal for the deterministic phase

## Branch Strategy

- `main` - Production-ready code
- `develop` - Integration branch
- `feat/*` - Feature branches

```bash
git checkout -b feat/<feature-name> develop
# work, then PR into develop
```

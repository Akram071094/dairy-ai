# AI Coding Assistant Instructions

## Overview

This document provides guidelines for AI coding assistants working on the Dairy AI Recommendation Engine (dairy-ai) repository.

## This Repository Handles

- AI-powered recommendation generation (deterministic engine today, Ollama later)
- Consuming operational data from the **shared PostgreSQL database** (owned by dairy-platform/dairy-backend schema)
- Exposing recommendation capabilities as a FastAPI service deployed separately from dairy-backend

## This Repository Does NOT Handle

- Business CRUD APIs (those live in dairy-backend)
- Database schema design, migrations, or RLS (owned by dairy-platform)
- Authentication/authorization (dairy-backend owns that; dairy-ai reads shared tables)

## Critical Rules

### 1. Never Change Database Schema

```markdown
✅ DO: Consume existing tables (inventory, stock_movements, outstandings, retailers, ...)
✅ DO: Read columns defined by dairy-backend models
✅ DO: Create/manage dairy-ai-owned tables only: ai_recommendations
❌ DON'T: Modify column types
❌ DON'T: Add new columns
❌ DON'T: Create tables outside the dairy-ai-owned list above
```

### 2. Read-Only Data Access

```markdown
✅ DO: Run SELECT queries against the shared PostgreSQL DB
✅ DO: Write only to the dairy-ai-owned ai_recommendations table (via the async job)
❌ DON'T: INSERT/UPDATE/DELETE operational data
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

- Routes: `app/api/<feature>/*.py` (e.g., recommendations.py, health.py; registered via `app/api/<feature>/__init__.py`)
- Services: `app/services/*_service.py`
- Schemas: `app/models/schemas.py`
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

#!/bin/bash
set -e

python -m scripts.run_migrations

exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1}
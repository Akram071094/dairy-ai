#!/usr/bin/env bash
set -euo pipefail

# Ensure dairy-ai-owned tables exist and verify DB connectivity before
# the server starts accepting traffic.
python -m scripts.run_migrations

# Replace the shell with uvicorn so it becomes PID 1 (correct signal
# handling) and binds to the port Render assigns via $PORT.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

"""Deterministic decision engine (rule-based, no ML models yet).

Computes recommendations from operational data using pure backend
calculations. Ollama/LLM integration will replace the scoring logic later
while keeping the API contract unchanged.
"""

from __future__ import annotations

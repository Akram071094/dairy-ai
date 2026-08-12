"""General-purpose utility functions."""

from __future__ import annotations

import logging
from typing import Any

LOGGER_NAME = "dairy_ai"


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger child of the root *dairy_ai* logger."""
    logger = logging.getLogger(f"{LOGGER_NAME}.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def clamp(value: float, low: float, high: float) -> float:
    """Clamp *value* into the inclusive range ``[low, high]``."""
    return max(low, min(high, value))


def to_float(value: Any, default: float = 0.0) -> float:
    """Safely coerce *value* to ``float``, returning *default* on failure."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

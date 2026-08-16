"""Generate recommendations from the CLI against the shared database.

Usage:
    python -m scripts.generate_recommendations --org-id <uuid> --domain stock --top-n 5
"""

from __future__ import annotations

import argparse
import logging
import uuid

from app.database import SessionLocal
from app.models.schemas import RecommendationDomain
from app.services.recommendation_service import RecommendationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scripts.recommend")


def main() -> None:
    """Entry point for the CLI recommendation runner."""
    parser = argparse.ArgumentParser(description="Run a recommendation domain.")
    parser.add_argument("--org-id", type=uuid.UUID, required=True, help="Organization UUID.")
    parser.add_argument(
        "--domain",
        type=RecommendationDomain,
        choices=tuple(RecommendationDomain),
        default=RecommendationDomain.STOCK,
    )
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        service = RecommendationService(db)
        result = service.recommend(args.org_id, args.domain, top_n=args.top_n)
        for item in result.recommendations:
            logger.info("%s | score=%.3f | %s", item.label, item.score, item.reason)
    finally:
        db.close()


if __name__ == "__main__":
    main()

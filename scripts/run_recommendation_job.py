"""Scheduled/async job: precompute recommendations into the shared table.

Writes the output of the decision engine into ``ai_recommendations`` so
dairy-backend (or the UI) can serve them without running ML logic in the
request path.

Usage:
    python -m scripts.run_recommendation_job --org-id <uuid> [--domain stock|collections] [--top-n 50]
    python -m scripts.run_recommendation_job                        # all orgs, all domains
"""

from __future__ import annotations

import argparse
import logging
import uuid

from sqlalchemy import delete

from app.database import Base, SessionLocal, engine
from app.models.recommendation import AIRecommendation
from app.models.schemas import RecommendationDomain
from app.services.recommendation_service import RecommendationService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scripts.recommendation_job")

_DOMAINS = tuple(RecommendationDomain)


def _populate_orgs(db) -> list[uuid.UUID]:
    """Discover active organizations from the shared organizations table."""
    from sqlalchemy import text

    rows = db.execute(text("SELECT id FROM organizations WHERE is_deleted = FALSE")).scalars().all()
    return [r for r in rows if r is not None]


def _upsert(
    db,
    organization_id: uuid.UUID,
    domain: RecommendationDomain,
    result,
) -> None:
    """Replace stored rows for (org, domain) with fresh precomputed ones.
    ``result`` is a ``RecommendationResponse`` from the service."""
    run_id = uuid.uuid4()
    db.execute(
        delete(AIRecommendation).where(
            AIRecommendation.organization_id == organization_id,
            AIRecommendation.domain == domain.value,
        )
    )
    for item in result.recommendations:
        db.add(
            AIRecommendation(
                organization_id=organization_id,
                domain=domain.value,
                item_id=item.item_id,
                label=item.label,
                score=item.score,
                reason=item.reason,
                run_id=run_id,
            )
        )
    db.commit()


def run_job(
    org_ids: list[uuid.UUID] | None = None, domain: RecommendationDomain | None = None
) -> int:
    """Compute and store recommendations; returns the number of rows written."""
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    written = 0
    try:
        orgs = org_ids or _populate_orgs(db)
        domains = (domain,) if domain else _DOMAINS
        service = RecommendationService(db)

        for org_id in orgs:
            for dom in domains:
                try:
                    result = service.recommend(org_id, dom, top_n=50)
                    _upsert(db, org_id, dom, result)
                    written += len(result.recommendations)
                    logger.info(
                        "stored domain=%s org=%s items=%d",
                        dom.value,
                        org_id,
                        len(result.recommendations),
                    )
                except Exception as exc:  # pragma: no cover - per-domain resilience
                    logger.warning("domain=%s org=%s failed: %s", dom.value, org_id, exc)
    finally:
        db.close()
    logger.info("job complete: %d recommendation rows", written)
    return written


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Precompute AI recommendations.")
    parser.add_argument("--org-id", type=uuid.UUID, default=None)
    parser.add_argument("--domain", type=str, choices=[c.value for c in _DOMAINS], default=None)
    args = parser.parse_args()

    domain_enum = RecommendationDomain(args.domain) if args.domain else None
    run_job(org_ids=[args.org_id] if args.org_id else None, domain=domain_enum)


if __name__ == "__main__":
    main()

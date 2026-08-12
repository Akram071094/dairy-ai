"""Operational data access service.

Fetches operational data from the shared PostgreSQL database (the same
schema consumed by dairy-backend) and packages it into Pandas DataFrames
for the decision engine.
"""

from __future__ import annotations

import uuid
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.exceptions.errors import DatabaseError


class DataService:
    """Read-only data access from the shared PostgreSQL database."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def fetch_inventory(self, organization_id: uuid.UUID) -> pd.DataFrame:
        """Return active inventory rows for *organization_id*."""
        query = text(
            """
            SELECT sku_id, sku_code, sku_name,
                   available_quantity, low_stock_threshold,
                   reserved_quantity, total_quantity, unit
            FROM inventory
            WHERE organization_id = :org_id AND is_deleted = FALSE
            """
        )
        return self._run_query(query, org_id=organization_id)

    def fetch_stock_movements(self, organization_id: uuid.UUID, days: int = 30) -> pd.DataFrame:
        """Return outbound stock movements for *organization_id* in the last *days*."""
        query = text(
            """
            SELECT sku_id, sku_code, movement_type, quantity, effective_date
            FROM stock_movements
            WHERE organization_id = :org_id
              AND movement_type = 'stock_out'
              AND effective_date >= CURRENT_DATE - (:days * INTERVAL '1 day')
            """
        )
        return self._run_query(query, org_id=organization_id, days=days)

    def fetch_outstandings(self, organization_id: uuid.UUID) -> pd.DataFrame:
        """Return retailer outstanding/credit balances for *organization_id*."""
        query = text(
            """
            SELECT retailer_id, outstanding_amount, credit_limit,
                   available_credit, overdue_amount
            FROM outstandings
            WHERE organization_id = :org_id
            """
        )
        return self._run_query(query, org_id=organization_id)

    def fetch_retailers(self, organization_id: uuid.UUID) -> pd.DataFrame:
        """Return retailer display names for *organization_id*."""
        query = text(
            """
            SELECT id AS retailer_id, display_name, business_code
            FROM retailers
            WHERE organization_id = :org_id AND is_deleted = FALSE
            """
        )
        return self._run_query(query, org_id=organization_id)

    def _run_query(self, query: Any, **params: Any) -> pd.DataFrame:
        """Execute *query* and return the results as a DataFrame."""
        try:
            with self.db as session:
                result = session.execute(query, params)
                rows = result.mappings().all()
                if not rows:
                    return pd.DataFrame()
                return pd.DataFrame(rows)
        except Exception as exc:  # pragma: no cover - depends on DB availability
            raise DatabaseError(f"Failed to query operational data: {exc}") from exc

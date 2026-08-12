"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app

ORG_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Yield a FastAPI TestClient wrapping the application."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_inventory() -> pd.DataFrame:
    """Return a small synthetic inventory frame."""
    return pd.DataFrame(
        {
            "sku_id": [
                uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"),
                uuid.UUID("aaaaaaaa-0000-0000-0000-000000000002"),
                uuid.UUID("aaaaaaaa-0000-0000-0000-000000000003"),
            ],
            "sku_code": ["MILK-1L", "CURD-500", "GHEE-1L"],
            "sku_name": ["Fresh Milk 1L", "Curd 500g", "Ghee 1L"],
            "available_quantity": [5.0, 3.0, 40.0],
            "low_stock_threshold": [10.0, 10.0, 10.0],
            "reserved_quantity": [0.0, 0.0, 0.0],
            "total_quantity": [5.0, 3.0, 40.0],
            "unit": ["liters", "grams", "liters"],
        }
    )


@pytest.fixture
def sample_stock_movements() -> pd.DataFrame:
    """Return a small synthetic outbound stock movements frame."""
    return pd.DataFrame(
        {
            "sku_id": [
                uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"),
                uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001"),
                uuid.UUID("aaaaaaaa-0000-0000-0000-000000000002"),
            ],
            "sku_code": ["MILK-1L", "MILK-1L", "CURD-500"],
            "movement_type": ["stock_out", "stock_out", "stock_out"],
            "quantity": [4.0, 4.0, 0.5],
            "effective_date": pd.to_datetime(["2026-08-11", "2026-08-10", "2026-08-11"]),
        }
    )


@pytest.fixture
def sample_outstandings() -> pd.DataFrame:
    """Return a small synthetic outstandings frame."""
    return pd.DataFrame(
        {
            "retailer_id": [
                uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001"),
                uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002"),
                uuid.UUID("bbbbbbbb-0000-0000-0000-000000000003"),
            ],
            "outstanding_amount": [10000.0, 5000.0, 200.0],
            "credit_limit": [20000.0, 20000.0, 20000.0],
            "available_credit": [0.0, 10000.0, 18000.0],
            "overdue_amount": [4000.0, 1000.0, 0.0],
        }
    )


@pytest.fixture
def sample_retailers() -> pd.DataFrame:
    """Return a small synthetic retailers frame."""
    return pd.DataFrame(
        {
            "retailer_id": [
                uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001"),
                uuid.UUID("bbbbbbbb-0000-0000-0000-000000000002"),
                uuid.UUID("bbbbbbbb-0000-0000-0000-000000000003"),
            ],
            "display_name": ["Anand General Store", "Shree Kirana", "Green Mart"],
            "business_code": ["RT-001", "RT-002", "RT-003"],
        }
    )

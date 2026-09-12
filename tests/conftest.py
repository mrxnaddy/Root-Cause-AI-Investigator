"""
conftest.py
-----------
Makes the project root importable from tests/ (so `from utils import ...`
works without installing the project as a package), and holds fixtures
shared across multiple test files.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import pandas as pd


@pytest.fixture
def sample_sales_df():
    return pd.DataFrame({
        "date": pd.date_range("2025-08-08", periods=13, freq="D").strftime("%Y-%m-%d"),
        "revenue": [18200, 17950, 18400, 18100, 16850, 15200, 14100, 13250, 13580, 13020, 13390, 17600, 18050],
        "orders": [412, 405, 420, 410, 381, 338, 305, 286, 290, 275, 281, 398, 409],
    })


@pytest.fixture
def sample_root_cause():
    return {
        "description": "Mobile checkout/payment failure introduced by campaign v4's new redirect flow",
        "confidence": 87,
        "supporting_evidence": ["Error logs show 502s", "Complaints match timeline", "Mobile conversion crashed"],
        "evidence_sources": ["error_logs.txt", "complaints.txt", "ga_export.csv", "sales.csv"],
    }


@pytest.fixture
def sample_alternatives():
    return [
        {"description": "Ad-quality deterioration", "confidence": 21, "evidence_sources": ["ad_spend.csv"]},
        {"description": "Inventory shortage", "confidence": 8, "evidence_sources": []},
    ]
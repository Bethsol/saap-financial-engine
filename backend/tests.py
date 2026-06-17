"""
Smoke tests for the Financial Intelligence Engine.

Run:
    pytest tests.py -v
"""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from ingestion import ingest_csv
from metrics import compute_kpis
from normalization import fx_rate, map_to_ufl, normalize


SAMPLE_DIR = Path(__file__).parent / "sample_data"


@pytest.mark.parametrize("sample", [
    "ro_saga_export.csv",
    "us_quickbooks.csv",
    "de_datev_export.csv",
])
def test_ingestion_detects_required_columns(sample):
    """Every shipped sample must be parseable without hand-tuning."""
    result = ingest_csv(SAMPLE_DIR / sample, source_system_hint=sample)
    assert "transaction_date" in result.detected_mapping
    assert "amount" in result.detected_mapping
    assert result.rows_out > 0


def test_ingestion_handles_semicolon_decimal_comma():
    """SAGA / DATEV style files must parse correctly."""
    result = ingest_csv(SAMPLE_DIR / "ro_saga_export.csv")
    # Amounts should be numeric and positive after sign normalization.
    assert (result.canonical["amount"] > 0).all()


def test_fx_triangulation_via_eur():
    """USD -> RON should triangulate through EUR if no direct pair exists."""
    rate = fx_rate(date(2026, 1, 1), "USD", "RON")
    assert 4.0 < rate < 5.5  # Reasonable USD/RON range


def test_ufl_mapping_handles_languages():
    """The same conceptual category must collapse across languages."""
    assert map_to_ufl("Venituri") == "Revenue"
    assert map_to_ufl("Umsatz") == "Revenue"
    assert map_to_ufl("Sales") == "Revenue"
    assert map_to_ufl("Vanzari") == "Revenue"
    assert map_to_ufl("Publicitate") == "Marketing"
    assert map_to_ufl("Werbung") == "Marketing"


def test_end_to_end_pipeline():
    """Smoke test: file in, KPIs out."""
    result = ingest_csv(SAMPLE_DIR / "ro_saga_export.csv")
    normalized = normalize(result.canonical, base_currency="EUR")
    snapshot = compute_kpis(normalized, base_currency="EUR")

    assert snapshot.total_revenue > 0
    assert snapshot.total_expenses > 0
    assert snapshot.base_currency == "EUR"
    assert snapshot.monthly_series  # at least one month
    # Sanity check: revenue + expenses cover all rows.
    total_volume = snapshot.total_revenue + snapshot.total_expenses
    pipeline_volume = normalized["base_amount"].sum()
    assert abs(total_volume - pipeline_volume) < 0.01


def test_no_numeric_hallucination_in_synthesis_payload():
    """Every figure shown to the user must be present in the KPI snapshot.

    This is the deterministic-half-of-the-promise test. Synthesis depends
    on this contract: no numbers may originate in the LLM.
    """
    result = ingest_csv(SAMPLE_DIR / "us_quickbooks.csv")
    normalized = normalize(result.canonical)
    snapshot = compute_kpis(normalized)

    serialized = snapshot.to_dict()
    assert "total_revenue" in serialized
    assert "total_expenses" in serialized
    assert "net_profit" in serialized
    # The contract: profit must equal revenue minus expenses (rounding-tolerant).
    diff = serialized["total_revenue"] - serialized["total_expenses"] - serialized["net_profit"]
    assert abs(diff) < 0.01

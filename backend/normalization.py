"""
Tier 1 (continued) — Normalization Engine.

Takes the canonical DataFrame produced by `ingestion.py` and applies two
transformations:

  1. Currency normalization: every transaction is converted to the client's
     base currency at the historically-correct rate for the transaction date.
  2. Fiscal label mapping: raw category strings (in any of the supported
     languages) are projected onto the Universal Financial Language (UFL)
     category set.

These transformations are isolated from ingestion so that we can rerun
normalization (e.g. when the FX table updates) without re-parsing source
files.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Iterable

import pandas as pd
from rapidfuzz import fuzz, process


# ---------------------------------------------------------------------------
# In-memory FX table.
#
# In production this is backed by `fx_rate` in the database, populated by a
# daily cron against the ECB reference rates feed. For the thesis prototype
# we ship a static table that demonstrates the mechanism.
# ---------------------------------------------------------------------------

_STATIC_FX: dict[tuple[str, str], float] = {
    ("RON", "EUR"): 0.2010,
    ("USD", "EUR"): 0.9200,
    ("GBP", "EUR"): 1.1600,
    ("CHF", "EUR"): 1.0400,
    ("EUR", "EUR"): 1.0000,
    ("EUR", "USD"): 1.0870,
    ("EUR", "RON"): 4.9750,
}


def fx_rate(d: date, from_ccy: str, to_ccy: str) -> float:
    """Return the FX rate for a given date.

    The static table ignores `d` (uses spot rate). Replace this function in
    production with a query against the `fx_rate` table.
    """
    if from_ccy == to_ccy:
        return 1.0
    key = (from_ccy.upper(), to_ccy.upper())
    if key in _STATIC_FX:
        return _STATIC_FX[key]
    # Triangulate through EUR if direct pair not present.
    eur_leg_a = _STATIC_FX.get((from_ccy.upper(), "EUR"))
    eur_leg_b = _STATIC_FX.get(("EUR", to_ccy.upper()))
    if eur_leg_a is not None and eur_leg_b is not None:
        return eur_leg_a * eur_leg_b
    raise ValueError(f"No FX rate available for {from_ccy} -> {to_ccy}")


# ---------------------------------------------------------------------------
# Universal Financial Language (UFL) mapping.
# ---------------------------------------------------------------------------

UFL_DICTIONARY: dict[str, str] = {
    # English
    "revenue": "Revenue", "sales": "Revenue", "income": "Revenue",
    "marketing": "Marketing", "advertising": "Marketing", "ads": "Marketing",
    "payroll": "Payroll", "salaries": "Payroll", "wages": "Payroll",
    "logistics": "Logistics", "courier": "Logistics", "fuel": "Logistics",
    "shipping": "Logistics", "freight": "Logistics",
    "rent": "Facilities", "office": "Facilities", "utilities": "Facilities",
    "software": "Technology", "subscriptions": "Technology",
    "saas": "Technology", "hosting": "Technology",
    # Romanian
    "venituri": "Revenue", "vanzari": "Revenue",
    "publicitate": "Marketing", "reclama": "Marketing",
    "salarii": "Payroll",
    "transport": "Logistics", "combustibil": "Logistics", "curier": "Logistics",
    "chirie": "Facilities",
    "abonamente": "Technology",
    # German
    "umsatz": "Revenue", "erloese": "Revenue", "verkauf": "Revenue",
    "werbung": "Marketing",
    "gehaelter": "Payroll", "loehne": "Payroll",
    "versand": "Logistics", "treibstoff": "Logistics",
    "miete": "Facilities",
    "abonnements": "Technology", "software_lizenzen": "Technology",
}

UFL_CATEGORIES = sorted(set(UFL_DICTIONARY.values())) + ["Other"]


@lru_cache(maxsize=4096)
def map_to_ufl(raw_label: str) -> str:
    """Map any raw label string to the UFL category set.

    Uses cached fuzzy matching — the same raw labels appear thousands of
    times in a transaction file, so the cache pays for itself immediately.
    """
    if not raw_label:
        return "Other"
    cleaned = _strip(raw_label)
    if cleaned in UFL_DICTIONARY:
        return UFL_DICTIONARY[cleaned]
    match = process.extractOne(
        cleaned, list(UFL_DICTIONARY.keys()), scorer=fuzz.token_set_ratio
    )
    if match is None:
        return "Other"
    key, score, _ = match
    return UFL_DICTIONARY[key] if score >= 70 else "Other"


def _strip(s: str) -> str:
    s = s.lower().strip()
    translations = str.maketrans({
        "ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s",
        "ț": "t", "ţ": "t", "ö": "o", "ü": "u", "ä": "a", "ß": "ss",
    })
    return s.translate(translations)


# ---------------------------------------------------------------------------
# Pipeline-facing API
# ---------------------------------------------------------------------------

def normalize(
    df: pd.DataFrame,
    *,
    base_currency: str = "EUR",
) -> pd.DataFrame:
    """Apply FX + fiscal label normalization to a canonical DataFrame.

    Expects the DataFrame produced by `ingestion.ingest_csv` (columns:
    transaction_date, amount, description, raw_category, source_currency,
    direction).

    Returns a new DataFrame with two additional columns:
      - base_amount        : amount in base_currency
      - universal_category : UFL classification of raw_category
      - fx_rate            : the conversion rate used (for audit)
    """
    out = df.copy()
    out["fx_rate"] = [
        fx_rate(d.date(), c, base_currency)
        for d, c in zip(out["transaction_date"], out["source_currency"])
    ]
    out["base_amount"] = (out["amount"] * out["fx_rate"]).round(4)
    out["universal_category"] = out["raw_category"].apply(map_to_ufl)
    return out


def summarize_by_category(
    df: pd.DataFrame,
    *,
    direction: str | None = None,
) -> pd.DataFrame:
    """Helper used by the metrics layer."""
    work = df if direction is None else df[df["direction"] == direction]
    return (
        work.groupby("universal_category")["base_amount"]
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )

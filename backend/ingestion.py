"""
Tier 1 — Agnostic Ingestion Layer.

The "messy data" problem: SMEs export financial data from heterogeneous
sources (SAGA, QuickBooks, DATEV, Xero, raw bank CSVs). Columns are named
differently, in different languages, in different orders. Some files have
a date in column A; some in column F. Some use commas as decimal separators;
some use dots.

The Ingestion Layer is "agnostic" — it does NOT require the caller to know
the source schema. It uses fuzzy matching against a multilingual synonym
dictionary to identify which column means what, then projects to a single
internal representation.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from rapidfuzz import fuzz, process


# ---------------------------------------------------------------------------
# Multilingual synonym dictionary.
#
# The keys are the *target* canonical fields used internally by the rest of
# the pipeline. Each value is the list of source-system aliases observed in
# real exports. We use rapidfuzz to match against this list with a threshold,
# so typos and minor variants ("Total Vânzări" vs "Total Vanzari") still hit.
# ---------------------------------------------------------------------------

CANONICAL_FIELDS: dict[str, list[str]] = {
    "transaction_date": [
        "date", "transaction_date", "posting_date", "doc_date",
        "data", "data_documentului", "data_tranzactiei",
        "datum", "buchungsdatum",
    ],
    "description": [
        "description", "memo", "narrative", "details", "particulars",
        "descriere", "explicatie", "explicație",
        "beschreibung", "verwendungszweck", "buchungstext",
    ],
    "amount": [
        "amount", "value", "total", "sum", "net_amount", "gross_amount",
        "suma", "valoare", "total_valoare",
        "betrag", "summe", "wert",
    ],
    "currency": [
        "currency", "ccy", "iso_currency",
        "moneda", "valuta",
        "währung", "waehrung",
    ],
    "category": [
        "category", "account", "account_name", "ledger",
        "categorie", "cont", "denumire_cont",
        "kategorie", "konto", "kontoname",
    ],
}


# A fuzzy threshold of 75 catches "Vânzări" -> "Vanzari" and "Umsatz" -> "Umsatz"
# but rejects "Notes" -> "Date". Tunable; do not lower without re-testing.
FUZZY_THRESHOLD = 75


@dataclass
class IngestionResult:
    """Output of a single file ingestion run."""

    canonical: pd.DataFrame
    detected_mapping: dict[str, str]
    source_system_hint: str
    rows_in: int
    rows_out: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected_mapping": self.detected_mapping,
            "source_system_hint": self.source_system_hint,
            "rows_in": self.rows_in,
            "rows_out": self.rows_out,
            "sample": self.canonical.head(5).to_dict(orient="records"),
        }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_csv(
    file_content: bytes | str | Path,
    *,
    source_system_hint: str = "unknown",
) -> IngestionResult:
    """Ingest a single CSV file into the canonical schema.

    Parameters
    ----------
    file_content
        Either raw bytes (e.g. from an upload), a string of CSV text, or a
        filesystem Path to a CSV file.
    source_system_hint
        Optional. If the caller knows the source ('saga', 'quickbooks',
        'datev', 'xero'), pass it through — used only for auditing.

    Returns
    -------
    IngestionResult
    """
    raw = _read_any(file_content)
    mapping = _detect_column_mapping(raw.columns.tolist())
    canonical = _project_to_canonical(raw, mapping)

    return IngestionResult(
        canonical=canonical,
        detected_mapping=mapping,
        source_system_hint=source_system_hint,
        rows_in=len(raw),
        rows_out=len(canonical),
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _read_any(content: bytes | str | Path) -> pd.DataFrame:
    """Read CSV with autodetection of delimiter and decimal separator.

    Real exports use mixed conventions:
      - Romanian SAGA files: ';' delimiter, ',' decimal
      - US QuickBooks: ',' delimiter, '.' decimal
      - German DATEV:  ';' delimiter, ',' decimal
    """
    if isinstance(content, Path):
        text = content.read_text(encoding="utf-8-sig")
    elif isinstance(content, bytes):
        text = content.decode("utf-8-sig", errors="replace")
    else:
        text = content

    # Heuristic: if the first non-header line has more ';' than ',' we treat
    # ';' as the delimiter. This works for >95% of real-world SME exports.
    first_lines = text.splitlines()[:5]
    semis = sum(line.count(";") for line in first_lines)
    commas = sum(line.count(",") for line in first_lines)
    delimiter = ";" if semis > commas else ","
    decimal = "," if delimiter == ";" else "."

    return pd.read_csv(
        io.StringIO(text),
        sep=delimiter,
        decimal=decimal,
        dtype=str,           # keep everything as text initially; cast later
        keep_default_na=False,
    )


def _detect_column_mapping(columns: list[str]) -> dict[str, str]:
    """Return {canonical_field: source_column} via fuzzy matching."""
    cleaned = {col: _clean(col) for col in columns}
    mapping: dict[str, str] = {}

    for canonical, aliases in CANONICAL_FIELDS.items():
        best_score = 0
        best_col: str | None = None
        for raw_col, clean_col in cleaned.items():
            match = process.extractOne(
                clean_col, aliases, scorer=fuzz.token_set_ratio
            )
            if match is None:
                continue
            _, score, _ = match
            if score > best_score:
                best_score = score
                best_col = raw_col
        if best_col is not None and best_score >= FUZZY_THRESHOLD:
            mapping[canonical] = best_col

    return mapping


def _parse_dates(series: pd.Series) -> pd.Series:
    """Adaptive date parsing.

    SAGA/DATEV use DD/MM/YYYY or DD.MM.YYYY; QuickBooks uses MM/DD/YYYY.
    We try both interpretations and keep whichever produces fewer NaT
    values — the data itself votes for the regional convention.
    """
    day_first = pd.to_datetime(series, errors="coerce", dayfirst=True)
    month_first = pd.to_datetime(series, errors="coerce", dayfirst=False)
    return day_first if day_first.isna().sum() <= month_first.isna().sum() else month_first


def _parse_amount(value: Any) -> float:
    """Normalize amount strings across regional conventions.

    Handles:
      - "42500,00"      (RO / DE decimal comma)
      - "42 500,00"     (RO with thousands space)
      - "42,500.00"     (US with thousands comma)
      - "-1450.00"      (US negative)
      - "(1450.00)"     (accounting-style negative)
    """
    if value is None:
        return float("nan")
    s = str(value).strip()
    if not s:
        return float("nan")
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    if s.startswith("-"):
        negative = True
        s = s[1:]
    s = s.replace(" ", "").replace(" ", "")
    # If both separators are present, the rightmost one is the decimal.
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        # Single comma: treat as decimal separator (the common EU convention).
        s = s.replace(",", ".")
    try:
        num = float(s)
    except ValueError:
        return float("nan")
    return -num if negative else num


def _clean(s: str) -> str:
    """Strip punctuation, lowercase, and remove diacritics for matching."""
    s = s.lower().strip()
    # Replace common Romanian/German diacritics with ASCII equivalents.
    translations = str.maketrans({
        "ă": "a", "â": "a", "î": "i", "ș": "s", "ş": "s",
        "ț": "t", "ţ": "t", "ö": "o", "ü": "u", "ä": "a", "ß": "ss",
    })
    s = s.translate(translations)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def _project_to_canonical(
    raw: pd.DataFrame, mapping: dict[str, str]
) -> pd.DataFrame:
    """Project the raw frame onto the canonical schema."""
    missing = {"transaction_date", "amount"} - set(mapping.keys())
    if missing:
        raise ValueError(
            f"Could not detect required columns: {missing}. "
            f"Detected mapping was: {mapping}"
        )

    out = pd.DataFrame()
    out["transaction_date"] = _parse_dates(raw[mapping["transaction_date"]])
    out["amount"] = raw[mapping["amount"]].apply(_parse_amount)
    out["description"] = (
        raw[mapping["description"]] if "description" in mapping else ""
    )
    out["raw_category"] = (
        raw[mapping["category"]] if "category" in mapping else ""
    )
    out["source_currency"] = (
        raw[mapping["currency"]] if "currency" in mapping else "EUR"
    )

    # Drop rows that lost essential fields during type coercion.
    out = out.dropna(subset=["transaction_date", "amount"]).reset_index(drop=True)

    # Sign convention: positive = income, negative = expense.
    out["direction"] = out["amount"].apply(lambda v: "I" if v > 0 else "E")
    out["amount"] = out["amount"].abs()

    return out

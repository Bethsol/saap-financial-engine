"""
Tier 2 (deterministic half) — Metrics Engine.

This module is the Quantitative Layer described in the thesis. It produces
all numbers the dashboard and the AI ever see. The LLM is forbidden from
inventing digits; it can only interpret what `compute_kpis` returns.

Design rule: every function here is pure (no I/O, no model calls). This
makes the engine trivially unit-testable, which matters when the output
drives strategic business decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class KPISnapshot:
    """The deterministic snapshot fed to the LLM and to the dashboard."""

    period_start: str
    period_end: str
    base_currency: str

    # Top-line
    total_revenue: float
    total_expenses: float
    net_profit: float
    profit_margin_pct: float       # 0-100 scale

    # Trend
    revenue_trend_pct: float       # vs. prior comparable period
    expense_trend_pct: float

    # Health
    monthly_burn: float
    runway_months: float | None    # None if profitable
    expense_concentration_pct: float  # share of largest expense category

    # Distribution
    revenue_by_category: list[dict[str, Any]]
    expenses_by_category: list[dict[str, Any]]
    monthly_series: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Top-level entrypoint
# ---------------------------------------------------------------------------

def compute_kpis(
    df: pd.DataFrame,
    *,
    base_currency: str = "EUR",
    today: date | None = None,
) -> KPISnapshot:
    """Compute the KPI snapshot from a normalized DataFrame.

    The DataFrame is expected to be the output of `normalization.normalize`.
    """
    if df.empty:
        raise ValueError("compute_kpis received an empty DataFrame.")

    today = today or df["transaction_date"].max().date()
    period_start = df["transaction_date"].min().date()
    period_days = max((today - period_start).days, 1)

    income = df[df["direction"] == "I"]
    expense = df[df["direction"] == "E"]

    total_rev = float(income["base_amount"].sum())
    total_exp = float(expense["base_amount"].sum())
    net = total_rev - total_exp
    margin = (net / total_rev * 100) if total_rev else 0.0

    # ---- Trend: compare current half of the data window against prior half.
    mid = period_start + timedelta(days=period_days // 2)
    rev_now = income[income["transaction_date"] >= pd.Timestamp(mid)]["base_amount"].sum()
    rev_prev = income[income["transaction_date"] < pd.Timestamp(mid)]["base_amount"].sum()
    exp_now = expense[expense["transaction_date"] >= pd.Timestamp(mid)]["base_amount"].sum()
    exp_prev = expense[expense["transaction_date"] < pd.Timestamp(mid)]["base_amount"].sum()

    rev_trend = _pct_change(rev_prev, rev_now)
    exp_trend = _pct_change(exp_prev, exp_now)

    # ---- Burn / runway
    months_covered = max(period_days / 30.4375, 1)
    monthly_burn = max(total_exp - total_rev, 0) / months_covered
    runway = None  # Profitable businesses don't have a "runway"; surface as None.
    if monthly_burn > 0:
        # Without a balance figure, runway is "months at current loss to zero
        # net cumulative cash" — approximated from period totals.
        cumulative_net = total_rev - total_exp
        if cumulative_net < 0:
            runway = round(abs(cumulative_net) / monthly_burn, 1)

    # ---- Distribution
    rev_by_cat = (
        income.groupby("universal_category")["base_amount"]
        .sum().sort_values(ascending=False).reset_index()
        .rename(columns={"universal_category": "category", "base_amount": "amount"})
    )
    exp_by_cat = (
        expense.groupby("universal_category")["base_amount"]
        .sum().sort_values(ascending=False).reset_index()
        .rename(columns={"universal_category": "category", "base_amount": "amount"})
    )
    largest_exp_share = (
        (exp_by_cat["amount"].iloc[0] / total_exp * 100)
        if total_exp and not exp_by_cat.empty else 0.0
    )

    monthly = _monthly_series(df)

    return KPISnapshot(
        period_start=str(period_start),
        period_end=str(today),
        base_currency=base_currency,
        total_revenue=round(total_rev, 2),
        total_expenses=round(total_exp, 2),
        net_profit=round(net, 2),
        profit_margin_pct=round(margin, 2),
        revenue_trend_pct=round(rev_trend, 2),
        expense_trend_pct=round(exp_trend, 2),
        monthly_burn=round(monthly_burn, 2),
        runway_months=runway,
        expense_concentration_pct=round(largest_exp_share, 2),
        revenue_by_category=rev_by_cat.to_dict(orient="records"),
        expenses_by_category=exp_by_cat.to_dict(orient="records"),
        monthly_series=monthly,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pct_change(prev: float, curr: float) -> float:
    if prev == 0:
        return 0.0 if curr == 0 else 100.0
    return float((curr - prev) / prev * 100)


def _monthly_series(df: pd.DataFrame) -> list[dict[str, Any]]:
    work = df.copy()
    work["month"] = work["transaction_date"].dt.to_period("M").astype(str)
    grouped = (
        work.groupby(["month", "direction"])["base_amount"]
        .sum().unstack(fill_value=0.0).reset_index()
        .rename(columns={"I": "revenue", "E": "expenses"})
    )
    # Some months may have only one side; guarantee both columns exist.
    for col in ("revenue", "expenses"):
        if col not in grouped.columns:
            grouped[col] = 0.0
    grouped["net"] = grouped["revenue"] - grouped["expenses"]
    grouped = grouped.sort_values("month")
    return grouped[["month", "revenue", "expenses", "net"]].round(2).to_dict(orient="records")

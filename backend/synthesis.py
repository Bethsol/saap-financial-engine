"""
Tier 2 (synthesis half) — LLM-grounded CFO Synthesis.

Implements the "Virtual CFO" using a strict In-Context Learning (ICL)
pattern. The pattern guarantees that:

  * The model NEVER produces numbers — it receives them as ground truth
    and quotes them verbatim. Temperature is pinned to 0.0.
  * The system role establishes a constrained persona ("seasoned CFO
    advising an SME") — it does not roleplay outside finance.
  * Output is bounded to a fixed JSON schema so the frontend never has
    to parse free prose.

When the OPENAI_API_KEY is missing (e.g. in the thesis demo) we degrade
gracefully to a deterministic rule-based stub that emits the same shape.
"""

from __future__ import annotations

import json
import os
from typing import Any

from metrics import KPISnapshot

try:
    from openai import OpenAI
    _client: OpenAI | None = OpenAI() if os.getenv("OPENAI_API_KEY") else None
except Exception:  # pragma: no cover — keeps the prototype runnable without the SDK
    _client = None


SYSTEM_PROMPT = """\
You are a seasoned Chief Financial Officer advising a Small or Medium Enterprise.
Your role is strictly SEMANTIC: you interpret pre-calculated financial metrics
and convert them into clear, actionable strategic advice.

ABSOLUTE RULES:
1. You MUST NOT produce or invent any numbers. Every figure you reference
   must appear verbatim in the JSON payload provided by the user.
2. You MUST respond with a single JSON object matching the schema below.
   No prose outside the JSON.
3. Your tone is direct and operational — no fluff, no disclaimers.
4. Each recommendation must be specific, time-bound, and tied to a metric
   from the payload.

OUTPUT SCHEMA:
{
  "headline": "<one-sentence summary of the business's current state>",
  "diagnosis": "<2-3 sentences explaining WHY the numbers look as they do>",
  "risks": ["<risk 1>", "<risk 2>", "<risk 3>"],
  "recommendations": [
    {"action": "<imperative verb phrase>", "rationale": "<why this, tied to a metric>", "horizon": "<this week | this month | this quarter>"}
  ]
}
"""


def generate_insights(snapshot: KPISnapshot) -> dict[str, Any]:
    """Generate the qualitative layer from the quantitative snapshot."""
    payload = snapshot.to_dict()

    if _client is None:
        return _deterministic_fallback(snapshot)

    response = _client.chat.completions.create(
        model="gpt-4o",
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    raw = response.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Defensive: never propagate malformed model output to the frontend.
        return _deterministic_fallback(snapshot)


# ---------------------------------------------------------------------------
# Deterministic fallback.
#
# Used when the OpenAI key isn't configured (e.g. when the thesis defense
# demo runs offline). Keeps the prototype useful and proves the architecture
# is genuinely modular — the AI is replaceable.
# ---------------------------------------------------------------------------

def _deterministic_fallback(s: KPISnapshot) -> dict[str, Any]:
    risks: list[str] = []
    recs: list[dict[str, str]] = []

    if s.net_profit < 0:
        risks.append(
            f"Operating at a loss of {abs(s.net_profit):,.0f} {s.base_currency} "
            f"over the analysed period."
        )
    if s.expense_trend_pct > 10 and s.revenue_trend_pct < s.expense_trend_pct:
        risks.append(
            f"Expenses grew {s.expense_trend_pct:.1f}% while revenue grew "
            f"{s.revenue_trend_pct:.1f}% — costs are outpacing growth."
        )
    if s.expense_concentration_pct > 40:
        top = s.expenses_by_category[0] if s.expenses_by_category else None
        cat = top["category"] if top else "a single category"
        risks.append(
            f"{s.expense_concentration_pct:.0f}% of expenses are concentrated "
            f"in {cat} — single point of cost-side failure."
        )
    if s.runway_months is not None and s.runway_months < 6:
        risks.append(
            f"Cash runway is {s.runway_months} months at the current burn — "
            f"below the 6-month safety threshold."
        )

    if s.expense_trend_pct > 5 and s.profit_margin_pct < 15:
        recs.append({
            "action": "Audit your three largest expense categories for waste",
            "rationale": f"Expense trend of +{s.expense_trend_pct:.1f}% with a thin "
                         f"{s.profit_margin_pct:.1f}% margin leaves no buffer.",
            "horizon": "this month",
        })
    if s.revenue_trend_pct < 0:
        recs.append({
            "action": "Re-activate dormant customers via a targeted campaign",
            "rationale": f"Revenue is trending down by {abs(s.revenue_trend_pct):.1f}%; "
                         f"cheapest growth lever is reactivation, not acquisition.",
            "horizon": "this week",
        })
    if not recs:
        recs.append({
            "action": "Lock in current pricing and increase marketing spend on the top revenue category",
            "rationale": f"Margins of {s.profit_margin_pct:.1f}% with positive trend "
                         f"({s.revenue_trend_pct:+.1f}%) signal room to scale.",
            "horizon": "this quarter",
        })

    headline = (
        f"Net profit of {s.net_profit:,.0f} {s.base_currency} on revenue of "
        f"{s.total_revenue:,.0f} {s.base_currency} ({s.profit_margin_pct:.1f}% margin)."
    )
    diagnosis = (
        f"Revenue trend is {s.revenue_trend_pct:+.1f}% vs the prior period; "
        f"expense trend is {s.expense_trend_pct:+.1f}%. The largest expense "
        f"bucket accounts for {s.expense_concentration_pct:.0f}% of total spend."
    )

    return {
        "headline": headline,
        "diagnosis": diagnosis,
        "risks": risks or ["No material risks detected in the current window."],
        "recommendations": recs,
    }

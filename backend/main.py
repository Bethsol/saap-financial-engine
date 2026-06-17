"""
FastAPI entrypoint for the Financial Intelligence Engine.

Endpoints:
    GET  /health                 - liveness
    POST /ingest                 - upload a CSV (multipart) and get back a normalized snapshot
    GET  /dashboard/sample       - run the full pipeline against bundled sample data
    POST /analyze                - run on a JSON-supplied list of transactions

Run locally:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ingestion import ingest_csv
from metrics import compute_kpis
from normalization import normalize
from synthesis import generate_insights


app = FastAPI(
    title="SaaP Financial Intelligence Engine",
    version="0.1.0",
    description="Prototype for: 'Architecting a Global SaaP Framework' (thesis 2026).",
)

# Permissive CORS for the local Next.js dev server.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SAMPLE_DIR = Path(__file__).parent / "sample_data"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "ai": "live" if os.getenv("OPENAI_API_KEY") else "stub"}


@app.post("/ingest")
async def ingest(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file.")
    content = await file.read()
    try:
        result = ingest_csv(content, source_system_hint=file.filename)
    except ValueError as exc:
        raise HTTPException(422, str(exc))

    normalized = normalize(result.canonical)
    snapshot = compute_kpis(normalized)
    insights = generate_insights(snapshot)

    return {
        "ingestion": result.to_dict(),
        "metrics": snapshot.to_dict(),
        "insights": insights,
    }


@app.get("/dashboard/sample")
def dashboard_sample(source: str = "ro_saga_export.csv") -> dict[str, Any]:
    """Run the full pipeline against one of the bundled sample files."""
    path = SAMPLE_DIR / source
    if not path.exists():
        available = [p.name for p in SAMPLE_DIR.glob("*.csv")]
        raise HTTPException(404, f"Unknown sample. Available: {available}")
    result = ingest_csv(path, source_system_hint=path.stem)
    normalized = normalize(result.canonical)
    snapshot = compute_kpis(normalized)
    insights = generate_insights(snapshot)
    return {
        "ingestion": result.to_dict(),
        "metrics": snapshot.to_dict(),
        "insights": insights,
    }


class TransactionIn(BaseModel):
    transaction_date: str
    amount: float
    description: str = ""
    raw_category: str = ""
    source_currency: str = "EUR"
    direction: str = "E"  # 'I' or 'E'


@app.post("/analyze")
def analyze(transactions: list[TransactionIn]) -> dict[str, Any]:
    df = pd.DataFrame([t.model_dump() for t in transactions])
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df["amount"] = df["amount"].abs()
    normalized = normalize(df)
    snapshot = compute_kpis(normalized)
    insights = generate_insights(snapshot)
    return {"metrics": snapshot.to_dict(), "insights": insights}


# Serve the pre-built Next.js static export only in production.
# Set SERVE_FRONTEND=1 to activate (Dockerfile does this automatically).
# Local dev keeps port 8000 as API-only so the Next.js dev server on :3000
# remains the frontend.
_FRONTEND = Path(__file__).parent / "frontend_out"
if os.getenv("SERVE_FRONTEND") == "1" and _FRONTEND.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND), html=True), name="frontend")

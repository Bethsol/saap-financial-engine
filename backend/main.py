"""
FastAPI entrypoint for the Financial Intelligence Engine.

Endpoints:
    GET  /health                 - liveness
    POST /signup                 - create a new account
    POST /login                  - authenticate, get a token
    POST /ingest                 - upload a CSV (multipart), requires auth
    GET  /dashboard/sample       - run the full pipeline against bundled sample data, requires auth
    POST /analyze                - run on a JSON-supplied list of transactions, requires auth

Run locally:
    uvicorn main:app --reload --port 8000
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import (
    AuthResponse,
    LoginRequest,
    SignupRequest,
    get_current_user,
    init_db,
    login as auth_login,
    signup as auth_signup,
)
from ingestion import ingest_csv
from metrics import compute_kpis
from normalization import normalize
from synthesis import generate_insights


app = FastAPI(
    title="SaaP Financial Intelligence Engine",
    version="0.2.0",
    description="Prototype for: 'Architecting a Global SaaP Framework' (thesis 2026).",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SAMPLE_DIR = Path(__file__).parent / "sample_data"

init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "ai": "live" if os.getenv("OPENAI_API_KEY") else "stub"}


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.post("/signup", response_model=AuthResponse)
def signup(req: SignupRequest) -> AuthResponse:
    return auth_signup(req)


@app.post("/login", response_model=AuthResponse)
def login(req: LoginRequest) -> AuthResponse:
    return auth_login(req)


@app.get("/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    return user


# ---------------------------------------------------------------------------
# Protected business endpoints
# ---------------------------------------------------------------------------

@app.post("/ingest")
async def ingest(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
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
def dashboard_sample(
    source: str = "ro_saga_export.csv",
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
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
def analyze(
    transactions: list[TransactionIn],
    user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    df = pd.DataFrame([t.model_dump() for t in transactions])
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    df["amount"] = df["amount"].abs()
    normalized = normalize(df)
    snapshot = compute_kpis(normalized)
    insights = generate_insights(snapshot)
    return {"metrics": snapshot.to_dict(), "insights": insights}

"""
auth.py — Authentication module.

Real email/password authentication backed by SQLite. Passwords are hashed
with bcrypt (never stored in plain text). Sessions are managed via JWT
tokens, signed with a secret key, expiring after 7 days.

This module is self-contained: it creates its own SQLite database file
(users.db) on first run, with no external dependencies beyond bcrypt
and pyjwt.
"""

from __future__ import annotations

import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import Header, HTTPException
from pydantic import BaseModel, field_validator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production-please")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create the users table if it doesn't already exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id        TEXT PRIMARY KEY,
                email          TEXT UNIQUE NOT NULL,
                password_hash  TEXT NOT NULL,
                full_name      TEXT,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


@contextmanager
def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    email: str
    password: str
    full_name: str = ""

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not EMAIL_RE.match(v):
            raise ValueError("Invalid email address.")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user_id: str
    email: str
    full_name: str


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


# ---------------------------------------------------------------------------
# JWT token issuance / verification
# ---------------------------------------------------------------------------

def create_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid authentication token.")


# ---------------------------------------------------------------------------
# Core auth operations
# ---------------------------------------------------------------------------

def signup(req: SignupRequest) -> AuthResponse:
    with _get_conn() as conn:
        existing = conn.execute(
            "SELECT user_id FROM users WHERE email = ?", (req.email,)
        ).fetchone()
        if existing:
            raise HTTPException(409, "An account with this email already exists.")

        user_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users (user_id, email, password_hash, full_name) VALUES (?, ?, ?, ?)",
            (user_id, req.email, hash_password(req.password), req.full_name),
        )
        conn.commit()

    token = create_token(user_id, req.email)
    return AuthResponse(token=token, user_id=user_id, email=req.email, full_name=req.full_name)


def login(req: LoginRequest) -> AuthResponse:
    email = req.email.strip().lower()
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT user_id, email, password_hash, full_name FROM users WHERE email = ?",
            (email,),
        ).fetchone()

    if row is None or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(401, "Invalid email or password.")

    token = create_token(row["user_id"], row["email"])
    return AuthResponse(
        token=token,
        user_id=row["user_id"],
        email=row["email"],
        full_name=row["full_name"] or "",
    )


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """FastAPI dependency: extracts and verifies the bearer token from the
    Authorization header. Use as `user = Depends(get_current_user)` on any
    route that should require login.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or malformed Authorization header.")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)
    return {"user_id": payload["sub"], "email": payload["email"]}

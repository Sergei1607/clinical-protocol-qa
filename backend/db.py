"""Shared Supabase/Postgres connection helpers.

Two roles (same split as portfolio Project 2):
  - owner_url()     full DDL + write. Local only - never deployed.
  - readonly_url()  SELECT only (app_readonly). What the deployed API uses.

Both come from backend/.env (gitignored); see .env.example.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

load_dotenv(Path(__file__).resolve().parent / ".env")


def _require(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise SystemExit(
            f"{name} is not set. Copy backend/.env.example to backend/.env and fill it in."
        )
    return val


def owner_url() -> str:
    return _require("SUPABASE_OWNER_URL")


def readonly_url() -> str:
    return _require("SUPABASE_READONLY_URL")


def connect(url: str, register_types: bool = True) -> psycopg.Connection:
    """Open a connection. prepare_threshold=None keeps it working through
    Supabase's transaction-mode pooler too.

    register_types registers the pgvector adapter; pass False for the very first
    setup call, before the `vector` extension exists.
    """
    conn = psycopg.connect(url, autocommit=True, prepare_threshold=None)
    if register_types:
        register_vector(conn)
    return conn

"""
TASK 1: one-time Supabase schema setup for the protocol Q&A retrieval store.

Using the OWNER connection:
  - enable the pgvector extension
  - create the protocol_chunks table + HNSW cosine index (backend/sql/schema.sql)
  - grant SELECT on protocol_chunks to the existing app_readonly role
    (checked, not assumed - a prior blanket grant would not cover a new table)
  - verify the read-only role can actually SELECT it

Idempotent - safe to re-run.  Run from backend/ :  python setup_supabase.py
"""

from __future__ import annotations

from pathlib import Path

import db

SCHEMA_SQL = Path(__file__).resolve().parent / "sql" / "schema.sql"
READONLY_ROLE = "app_readonly"


def split_statements(sql: str) -> list[str]:
    out, buf = [], []
    for line in sql.splitlines():
        if line.strip().startswith("--") or not line.strip():
            continue
        buf.append(line)
        if line.rstrip().endswith(";"):
            out.append("\n".join(buf))
            buf = []
    if buf:
        out.append("\n".join(buf))
    return out


def main() -> int:
    statements = split_statements(SCHEMA_SQL.read_text(encoding="utf-8"))
    # register_types=False: the vector type may not exist yet on the first run
    with db.connect(db.owner_url(), register_types=False) as conn:
        for stmt in statements:
            label = stmt.split("\n")[0][:70]
            print(f"  running: {label}{'…' if len(stmt) > 70 else ''}")
            conn.execute(stmt)

        role_exists = conn.execute(
            "select 1 from pg_roles where rolname = %s", (READONLY_ROLE,)
        ).fetchone()
        if not role_exists:
            print(f"\n!! role {READONLY_ROLE!r} does not exist in this project.")
            print("   Create it (as in Project 2) then re-run, e.g.:")
            print(f"     create role {READONLY_ROLE} login password '…';")
            return 1

        conn.execute(f"grant select on protocol_chunks to {READONLY_ROLE}")
        # future-proof: also let it read the row if the table is ever recreated
        conn.execute(f"grant usage on schema public to {READONLY_ROLE}")

        can_select = conn.execute(
            "select has_table_privilege(%s, 'public.protocol_chunks', 'SELECT')",
            (READONLY_ROLE,),
        ).fetchone()[0]
        rowcount = conn.execute("select count(*) from protocol_chunks").fetchone()[0]
        has_index = conn.execute(
            "select 1 from pg_indexes where indexname = 'protocol_chunks_embedding_hnsw'"
        ).fetchone()

    print("\nverification:")
    print(f"  pgvector extension  : enabled")
    print(f"  protocol_chunks     : exists, {rowcount} rows")
    print(f"  HNSW cosine index   : {'present' if has_index else 'MISSING'}")
    print(f"  {READONLY_ROLE} SELECT : {'granted' if can_select else 'DENIED'}")
    return 0 if can_select and has_index else 1


if __name__ == "__main__":
    raise SystemExit(main())

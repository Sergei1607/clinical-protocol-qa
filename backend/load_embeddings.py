"""
TASK 2: embed every chunk in data/extracted/chunks.json with BAAI/bge-small-en-v1.5
and upsert it into protocol_chunks (OWNER connection).

bge-small-en-v1.5 convention: the "Represent this sentence for searching relevant
passages: " instruction is prepended to QUERIES only, never to passages. So the
chunk text here is embedded verbatim. (See test_retrieval.py for the query side.)

Idempotent: upsert keyed on chunk_id, so re-running after chunks.json changes
just refreshes rows (and deletes chunk_ids that no longer exist).

Run from backend/ :  python load_embeddings.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from sentence_transformers import SentenceTransformer

import db

CHUNKS_JSON = Path(__file__).resolve().parent.parent / "data" / "extracted" / "chunks.json"
MODEL_NAME = "BAAI/bge-small-en-v1.5"

COLUMNS = [
    "chunk_id", "section_number", "section_title", "breadcrumb",
    "page_start", "page_end", "text", "char_count", "is_partial_redaction",
    "sub_chunk_index", "n_sub_chunks", "source", "merged_from", "embedding",
]

UPSERT = f"""
insert into protocol_chunks ({", ".join(COLUMNS)})
values ({", ".join("%s" for _ in COLUMNS)})
on conflict (chunk_id) do update set
  {", ".join(f"{c} = excluded.{c}" for c in COLUMNS if c != "chunk_id")}
"""


def main() -> int:
    chunks = json.loads(CHUNKS_JSON.read_text(encoding="utf-8"))["chunks"]
    print(f"{len(chunks)} chunks from {CHUNKS_JSON.name}")

    t0 = time.perf_counter()
    model = SentenceTransformer(MODEL_NAME)
    print(f"loaded {MODEL_NAME} in {time.perf_counter() - t0:.1f}s")

    t0 = time.perf_counter()
    embeddings = model.encode(
        [c["text"] for c in chunks],          # passages: NO instruction prefix
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=True,
    )
    embed_s = time.perf_counter() - t0
    print(f"embedded {len(chunks)} chunks in {embed_s:.1f}s "
          f"({1000 * embed_s / len(chunks):.0f} ms/chunk), dim={embeddings.shape[1]}")

    rows = [
        (
            c["chunk_id"], c["section_number"], c["section_title"], c["breadcrumb"],
            c["page_start"], c["page_end"], c["text"], c["char_count"],
            c["is_partial_redaction"], c.get("sub_chunk_index"), c["n_sub_chunks"],
            c["source"], c.get("merged_from"), emb.tolist(),
        )
        for c, emb in zip(chunks, embeddings)
    ]

    t0 = time.perf_counter()
    with db.connect(db.owner_url()) as conn:
        with conn.cursor() as cur:
            cur.executemany(UPSERT, rows)
        keep = tuple(c["chunk_id"] for c in chunks)
        deleted = conn.execute(
            "delete from protocol_chunks where chunk_id <> all(%s)", (list(keep),)
        ).rowcount
        total = conn.execute("select count(*) from protocol_chunks").fetchone()[0]
    load_s = time.perf_counter() - t0

    print(f"\nupserted {len(rows)} rows in {load_s:.1f}s"
          + (f", deleted {deleted} stale rows" if deleted else ""))
    print(f"protocol_chunks now holds {total} rows")
    print(f"\ntotal (embed + load): {embed_s + load_s:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Retrieve-then-generate core for the protocol Q&A bot.

One pass: embed the question -> pgvector top-k against protocol_chunks (read-only
role) -> single Claude Messages call with a strict grounding system prompt ->
parse the machine-readable SOURCES block back out.

No tool-use loop - that pattern is already proven in Project 2 and isn't what's
new here. No auth / rate limiting on the endpoint either: acceptable for an
unlisted portfolio demo (same call as Projects 1 & 2); note for the README.
"""

from __future__ import annotations

import functools
import os
import re

import anthropic

import db
import embed_onnx

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_BACKEND = "onnxruntime"   # torch/sentence-transformers OOM'd Render's 512 MB free tier
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
REDACTION_MARKER = "[REDACTED: commercially confidential information]"  # from build_chunks.py

# Grounded extraction is well within Sonnet 5's range and the project has a hard
# "zero budget beyond tokens" constraint, so default to Sonnet, not Opus.
# Override with ANSWER_MODEL if answer quality ever needs it.
ANSWER_MODEL = os.environ.get("ANSWER_MODEL", "claude-sonnet-5")
DEFAULT_K = 8          # k=5 vs k=8 recheck: k=8 keeps the right chunk in-context for
                       # paraphrased questions without materially more token spend
MAX_TOKENS = 1200

SYSTEM_PROMPT = """You answer questions about ONE clinical trial protocol: Merck study \
MK-6482-005 / NCT04195750, an open-label Phase 3 study of belzutifan (MK-6482) versus \
everolimus in advanced renal cell carcinoma. You are given excerpts ("chunks") retrieved \
from the publicly posted protocol PDF.

Follow every rule:

1. Answer using ONLY the information in the provided chunks. Do not use outside knowledge \
about this drug, this trial, this disease, or how trials like this usually work. If the \
chunks do not contain the answer, say so plainly.

2. If a relevant chunk contains the marker "[REDACTED: commercially confidential \
information]", state that this specific information is redacted in the publicly posted \
protocol. Do not guess or infer what it might say.

3. If none of the provided chunks actually addresses the question, respond that the \
retrieved protocol excerpts do not contain that information. Do not fall back on what a \
trial like this "should" do. (Some of the protocol - notably the Schedule of Activities \
visit-by-visit table - is deliberately not in the retrieval set.)

4. Be concise and factual. Quote or closely paraphrase the chunk wording. Do not pad.

5. When a retrieved excerpt lists several distinct methods, criteria, steps, or facts that \
bear on the question, include all of them, not only the most prominent one. Completeness \
matters more than brevity when the excerpt itself enumerates multiple relevant items.

6. End EVERY response with a source list in exactly this format - a line reading SOURCES: \
on its own, then one line per section you actually drew on (not every chunk you were \
given):

SOURCES:
- §<section_number> | <section_title> | p.<page_start>-<page_end>

Use the section number, title and page range exactly as labelled on the chunk. If a \
section spans one page, still write it as p.N-N. If you could not answer from the chunks, \
write a SOURCES: line followed by a single line "- none"."""

_SOURCE_LINE = re.compile(
    r"^\s*[-*]\s*§?\s*(?P<num>[\w.]+)\s*\|\s*(?P<title>[^|]+?)\s*\|\s*"
    r"p\.?\s*(?P<p1>\d+)\s*(?:-\s*(?P<p2>\d+))?\s*$"
)


def warm() -> None:
    """Load the embedding model now (call from FastAPI startup)."""
    embed_onnx.warm()


def embed_query(question: str) -> list[float]:
    # bge convention: the query instruction is prepended to queries only.
    return embed_onnx.encode(QUERY_INSTRUCTION + question).tolist()


SEARCH_SQL = """
select chunk_id, section_number, section_title, breadcrumb,
       page_start, page_end, is_partial_redaction, text,
       1 - (embedding <=> %(q)s::vector) as similarity
from protocol_chunks
order by embedding <=> %(q)s::vector
limit %(k)s
"""


def search(question: str, k: int = DEFAULT_K) -> list[dict]:
    qv = embed_query(question)
    with db.connect(db.readonly_url()) as conn:      # per-request; fine at demo scale
        rows = conn.execute(SEARCH_SQL, {"q": qv, "k": k}).fetchall()
    cols = ["chunk_id", "section_number", "section_title", "breadcrumb",
            "page_start", "page_end", "is_partial_redaction", "text", "similarity"]
    return [dict(zip(cols, r)) for r in rows]


def _format_context(chunks: list[dict]) -> str:
    blocks = []
    for i, c in enumerate(chunks, 1):
        head = (f"[CHUNK {i}] §{c['section_number']} | {c['section_title']} | "
                f"p.{c['page_start']}-{c['page_end']}")
        blocks.append(f"{head}\n{c['text'].strip()}")
    return "\n\n".join(blocks)


def parse_sources(answer: str) -> list[dict]:
    if "SOURCES:" not in answer:
        return []
    tail = answer.rsplit("SOURCES:", 1)[1]
    out = []
    for line in tail.splitlines():
        if line.strip().lower() in ("- none", "-none", "* none"):
            return []
        m = _SOURCE_LINE.match(line)
        if m:
            out.append({
                "section_number": m["num"],
                "section_title": m["title"].strip(),
                "page_start": int(m["p1"]),
                "page_end": int(m["p2"] or m["p1"]),
            })
    return out


@functools.lru_cache(maxsize=1)
def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic()      # reads ANTHROPIC_API_KEY from env / .env


def _strip_breadcrumb(text: str) -> str:
    """Drop the leading '<breadcrumb> [i/n]' header line that build_chunks.py
    prepends - the Sources UI already shows section/title/page separately."""
    parts = text.split("\n\n", 1)
    if len(parts) == 2 and (" > " in parts[0] or parts[0].lstrip().startswith("§")
                            or re.match(r"^\d+(\.\d+)*\s", parts[0].strip())):
        return parts[1].strip()
    return text.strip()


def build_sources(citations: list[dict], chunks: list[dict]) -> list[dict]:
    """For each section Claude cited, attach the actual retrieved excerpt text.

    A cited section may map to several retrieved sub-chunks (e.g. 5.2/2 + 5.2/3);
    include all of them, in retrieval order. If a citation matches nothing that
    was retrieved (shouldn't happen given the system prompt), keep the metadata
    and flag it rather than dropping or erroring.
    """
    by_section: dict[str, list[dict]] = {}
    for c in chunks:
        by_section.setdefault(c["section_number"], []).append(c)

    sources = []
    for cit in citations:
        matched = by_section.get(cit["section_number"], [])
        excerpt = "\n\n———\n\n".join(_strip_breadcrumb(c["text"]) for c in matched)
        sources.append({
            "section_number": cit["section_number"],
            "section_title": cit["section_title"],
            "page_start": cit["page_start"],
            "page_end": cit["page_end"],
            "excerpt_text": excerpt or None,
            "is_partial_redaction": any(c["is_partial_redaction"] for c in matched),
            "contains_redaction_marker": REDACTION_MARKER in excerpt,
            "matched_retrieved_chunks": [c["chunk_id"] for c in matched],
            "unmatched": not matched,
        })
    return sources


def answer_question(question: str, k: int = DEFAULT_K) -> dict:
    chunks = search(question, k)
    user_msg = (
        f"Retrieved protocol excerpts:\n\n{_format_context(chunks)}\n\n"
        f"---\nQuestion: {question}"
    )
    resp = _client().messages.create(
        model=ANSWER_MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    answer = next((b.text for b in resp.content if b.type == "text"), "").strip()
    citations = parse_sources(answer)
    # answer     = raw model output incl. the SOURCES: block (used by eval / tests)
    # answer_text = display version: SOURCES: block stripped, since the structured
    #              `sources` list below carries it for the UI
    answer_text = re.split(r"\n+SOURCES:\s*", answer, maxsplit=1)[0].rstrip()

    return {
        "question": question,
        "answer": answer,
        "answer_text": answer_text,
        "citations": citations,
        "sources": build_sources(citations, chunks),
        "model": resp.model,
        "stop_reason": resp.stop_reason,
        "usage": {
            "input_tokens": resp.usage.input_tokens,
            "output_tokens": resp.usage.output_tokens,
        },
        "retrieved": [
            {
                "chunk_id": c["chunk_id"],
                "section_number": c["section_number"],
                "section_title": c["section_title"],
                "page_start": c["page_start"],
                "page_end": c["page_end"],
                "is_partial_redaction": c["is_partial_redaction"],
                "similarity": round(c["similarity"], 4),
            }
            for c in chunks
        ],
    }

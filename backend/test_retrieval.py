"""
TASK 3: manual retrieval validation - no FastAPI, no Claude yet.

Embeds a handful of realistic questions with the bge query instruction, runs a
pgvector cosine query against protocol_chunks via the READ-ONLY role, and prints
the top-5 chunks per question so we can eyeball whether retrieval lands on the
right sections before wiring in answer generation.

Run from backend/ :  python test_retrieval.py
"""

from __future__ import annotations

import textwrap

import embed_onnx

import db

QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

# deliberately varied: a summary-table question (needs the recovered Synopsis/§3),
# an eligibility question, a dose-modification question, one that should land on a
# partially-redacted section and show it, and one aimed at the excluded Schedule
# of Activities matrix (should NOT confidently answer).
QUESTIONS = [
    "What is the primary endpoint of this study?",
    "Can a patient who had major surgery three weeks ago be enrolled in the trial?",
    "How should belzutifan dosing be modified if a participant develops hypoxia?",
    "What are the tertiary and exploratory objectives and endpoints of the study?",
    "What is the full schedule of study assessments by visit week during the treatment period?",
    "Is this study open-label or blinded?",
]

TOPK = 5

SQL = """
select chunk_id, section_number, breadcrumb, is_partial_redaction,
       1 - (embedding <=> %(q)s::vector) as similarity, text
from protocol_chunks
order by embedding <=> %(q)s::vector
limit %(k)s
"""


def main() -> int:
    embed_onnx.warm()

    with db.connect(db.readonly_url()) as conn:
        # prove we are actually read-only
        who = conn.execute("select current_user").fetchone()[0]
        print(f"connected as: {who}\n")

        for i, q in enumerate(QUESTIONS, 1):
            qv = embed_onnx.encode(QUERY_INSTRUCTION + q).tolist()
            rows = conn.execute(SQL, {"q": qv, "k": TOPK}).fetchall()
            print("=" * 100)
            print(f"Q{i}. {q}")
            print("=" * 100)
            for cid, sec, crumb, redacted, sim, text in rows:
                snippet = " ".join(text.split())[:150]
                flag = "  [PARTIAL REDACTION]" if redacted else ""
                print(f"  {sim:.3f}  {cid:<11} §{sec:<9}{flag}")
                print(f"         {crumb}")
                print(textwrap.fill(snippet, width=94,
                                    initial_indent="         ", subsequent_indent="         "))
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

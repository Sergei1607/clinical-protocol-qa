"""
TASK 3: exercise the /ask logic (calls rag.answer_question directly - no server).

The original 6 retrieval-validation questions plus rephrasings of the two that
retrieved weakly ("primary endpoint", "major surgery"), to see whether Claude's
synthesis across the top-k chunks compensates when the exact right chunk isn't #1.

Run from backend/ :  python test_ask.py
"""

from __future__ import annotations

import textwrap

import rag

QUESTIONS = [
    # --- original 6 ---
    "What is the primary endpoint of this study?",
    "Can a patient who had major surgery three weeks ago be enrolled in the trial?",
    "How should belzutifan dosing be modified if a participant develops hypoxia?",
    "What are the tertiary and exploratory objectives and endpoints of the study?",
    "What is the full schedule of study assessments by visit week during the treatment period?",
    "Is this study open-label or blinded?",
    # --- rephrasings of the two weak retrievals ---
    "Which efficacy measure is the study's primary basis for comparing belzutifan to everolimus?",
    "How is progression-free survival defined in this trial?",
    "There's a washout or waiting period after major surgery before randomization - how long is it?",
    "If someone had a surgical procedure recently, does the protocol bar them from joining?",
]


def run() -> None:
    for i, q in enumerate(QUESTIONS, 1):
        r = rag.answer_question(q)
        print("=" * 100)
        print(f"Q{i}. {q}")
        print("-" * 100)
        print(textwrap.fill(r["answer"], width=100))
        print()
        print(f"  parsed citations: {r['citations']}")
        print(f"  model={r['model']}  stop={r['stop_reason']}  "
              f"tokens in/out={r['usage']['input_tokens']}/{r['usage']['output_tokens']}")
        print("  retrieved (chunk_id / §section / sim / redaction):")
        for c in r["retrieved"]:
            flag = " [PARTIAL REDACTION]" if c["is_partial_redaction"] else ""
            print(f"    {c['similarity']:.3f}  {c['chunk_id']:<12} §{c['section_number']}"
                  f" - {c['section_title'][:44]}{flag}")
        print()


if __name__ == "__main__":
    run()

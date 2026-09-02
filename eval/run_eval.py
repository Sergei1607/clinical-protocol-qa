"""
Evaluation harness for the clinical-protocol-qa RAG bot.

For every question in eval_set.json:
  1. Retrieval recall (programmatic, no LLM): did any expected_sections land in the
     top-k retrieved chunks, and at what rank?
  2. Answer correctness (LLM-as-judge, Claude Haiku): given the question, the
     generated answer, and the expected_behavior / expected_keyfacts rubric,
     return pass / fail / borderline + one sentence.

Writes eval/results.json (full detail) and eval/results.md (summary table).
Run from the repo root or from eval/:  python eval/run_eval.py
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
import rag  # noqa: E402

EVAL_SET = Path(__file__).resolve().parent / "eval_set.json"
# optional run label: `python run_eval.py v2` -> results_v2.json / results_v2.md,
# so a re-run after a prompt change doesn't clobber the baseline.
_TAG = f"_{sys.argv[1]}" if len(sys.argv) > 1 else ""
RESULTS_JSON = Path(__file__).resolve().parent / f"results{_TAG}.json"
RESULTS_MD = Path(__file__).resolve().parent / f"results{_TAG}.md"

# Judge model: tried claude-haiku-4-5 first (rubric grading is simpler than the
# generation call). On a first run Haiku got 17/18 judgments right but missed the
# one case with an `also_acceptable` fallback (q10) - it graded strictly against
# `expected_behavior` and ignored the fallback list. Sonnet handled that case
# correctly, so the harness uses Sonnet; the judge cost is trivial next to the
# generation calls anyway.
JUDGE_MODEL = "claude-sonnet-5"

JUDGE_SYSTEM = """You are grading a single answer produced by a retrieval-augmented \
Q&A bot that answers questions about ONE clinical trial protocol using only retrieved \
excerpts. You do NOT have the protocol. Judge the answer ONLY against the rubric given \
to you - do not use your own knowledge of the drug, the disease, or any published trial.

Behaviour definitions:
- "answer": a correct, grounded answer that conveys the substance of the expected key \
facts and does not refuse.
- "redacted": must state the information is redacted / commercially confidential / \
withheld in the public protocol, and must NOT state what the redacted content says.
- "not_in_excerpts": must make clear the requested information is not in the retrieved \
excerpts. Giving partial related information is fine ONLY if the answer also flags that \
the specific thing asked for is missing. Fabricating a confident answer is a fail.
- "should_refuse_outside_knowledge": must decline or defer and must NOT supply the \
outside fact (e.g. an approval status/date, or published results/numbers).

Grading:
- PASS: the answer satisfies the expected behaviour and (for "answer") conveys the core \
expected key facts. Small omissions of secondary detail are still a pass.
- BORDERLINE: mostly right but missing a core key fact, hedging oddly, or mixing a \
correct deferral with a small unsupported claim.
- FAIL: wrong behaviour (answered when it should have refused/deferred, or vice versa), \
fabricated content, contradicted a key fact, or omitted the central point.
IMPORTANT: if the rubric lists "also_acceptable" behaviours, the answer PASSES if it \
satisfies EITHER the expected_behavior OR any listed also_acceptable behaviour. For \
example, if expected_behavior is "answer" and also_acceptable is ["not_in_excerpts"], \
then an honest "that information isn't in the retrieved excerpts" is a PASS - do not \
fail it for not giving the substantive answer, and do not reason about what "should" \
have been retrievable.

Respond with these two lines and nothing else:
VERDICT: pass|fail|borderline
REASON: <one sentence>"""

_VERDICT_RE = re.compile(r"VERDICT[:\s]*\**\s*(pass|fail|borderline)", re.I)
_VERDICT_FALLBACK_RE = re.compile(r"\b(pass|fail|borderline)\b", re.I)
_REASON_RE = re.compile(r"REASON[:\s]*\**\s*(.+?)(?:\n\s*\n|$)", re.I | re.S)


def judge(client: anthropic.Anthropic, q: dict, answer: str) -> dict:
    rubric = {
        "question": q["question"],
        "expected_behavior": q["expected_behavior"],
        "also_acceptable": q.get("also_acceptable", []),
        "expected_keyfacts": q["expected_keyfacts"],
    }
    msg = (
        f"RUBRIC:\n{json.dumps(rubric, indent=2)}\n\n"
        f"BOT ANSWER TO GRADE:\n\"\"\"\n{answer}\n\"\"\""
    )
    resp = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=250,
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": msg}],
    )
    text = next((b.text for b in resp.content if b.type == "text"), "").strip()
    vm = _VERDICT_RE.search(text) or _VERDICT_FALLBACK_RE.search(text)
    rm = _REASON_RE.search(text)
    return {
        "verdict": vm.group(1).lower() if vm else "unparsed",
        "reasoning": " ".join((rm.group(1) if rm else text).split())[:400],
        "raw": text,
    }


def retrieval_recall(q: dict, retrieved: list[dict]) -> dict:
    ordered = [r["section_number"] for r in retrieved]
    wanted = q.get("expected_sections", [])
    hits = [(rank, s) for rank, s in enumerate(ordered, 1) if s in wanted]
    return {
        "checked": q.get("retrieval_check", False),
        "expected_sections": wanted,
        # section-granularity: for a split section this can be a hit even if the
        # specific sub-chunk carrying the answer wasn't retrieved (see q10).
        "retrieved_sections": ordered,
        "retrieved_chunk_ids": [r["chunk_id"] for r in retrieved],
        "found": bool(hits),
        "first_rank": hits[0][0] if hits else None,
        "n_expected_found": len({s for _, s in hits}),
        "n_expected_total": len(wanted),
    }


def main() -> int:
    spec = json.loads(EVAL_SET.read_text(encoding="utf-8"))
    questions = spec["questions"]
    client = anthropic.Anthropic()

    rag.warm()
    results = []
    for i, q in enumerate(questions, 1):
        t0 = time.perf_counter()
        out = rag.answer_question(q["question"])
        rec = retrieval_recall(q, out["retrieved"])
        verdict = judge(client, q, out["answer"])
        dt = time.perf_counter() - t0

        results.append({
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "expected_behavior": q["expected_behavior"],
            "also_acceptable": q.get("also_acceptable", []),
            "answer": out["answer"],
            "citations": out["citations"],
            "retrieval": rec,
            "retrieved": [
                {"rank": j, "chunk_id": r["chunk_id"], "section": r["section_number"],
                 "similarity": r["similarity"], "partial_redaction": r["is_partial_redaction"]}
                for j, r in enumerate(out["retrieved"], 1)
            ],
            "judge": verdict,
            "tokens": out["usage"],
            "seconds": round(dt, 1),
        })
        rk = f"rank {rec['first_rank']}" if rec["found"] else "MISS"
        rline = rk if rec["checked"] else f"{rk} (not scored)"
        print(f"  [{i:>2}/{len(questions)}] {q['id']}  judge={verdict['verdict']:<10} "
              f"retrieval={rline}")

    # ---- aggregates ----
    scored = [r for r in results if r["retrieval"]["checked"]]
    recall_hits = [r for r in scored if r["retrieval"]["found"]]
    passes = [r for r in results if r["judge"]["verdict"] == "pass"]
    fails = [r for r in results if r["judge"]["verdict"] == "fail"]
    borderline = [r for r in results if r["judge"]["verdict"] == "borderline"]

    summary = {
        "n_questions": len(results),
        "judge_pass": len(passes),
        "judge_borderline": len(borderline),
        "judge_fail": len(fails),
        "judge_pass_rate": round(len(passes) / len(results), 3),
        "retrieval_scored": len(scored),
        "retrieval_recall_hits": len(recall_hits),
        "retrieval_recall_rate": round(len(recall_hits) / len(scored), 3) if scored else None,
        "judge_model": JUDGE_MODEL,
        "answer_model": rag.ANSWER_MODEL,
        "k": rag.DEFAULT_K,
    }

    RESULTS_JSON.write_text(
        json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    _write_md(summary, results)

    print("\n" + "=" * 72)
    print(f"judge pass rate      : {len(passes)}/{len(results)}  "
          f"({summary['judge_pass_rate']:.0%})   "
          f"[borderline {len(borderline)}, fail {len(fails)}]")
    print(f"retrieval recall rate: {len(recall_hits)}/{len(scored)}  "
          f"({summary['retrieval_recall_rate']:.0%})   (scored questions only)")
    print("=" * 72)
    for r in fails + borderline:
        print(f"\n{r['id']} [{r['judge']['verdict'].upper()}] {r['question']}")
        print(f"  judge: {r['judge']['reasoning']}")
        print(f"  retrieval: found={r['retrieval']['found']} "
              f"rank={r['retrieval']['first_rank']} "
              f"expected={r['retrieval']['expected_sections']} "
              f"got={r['retrieval']['retrieved_sections'][:6]}")
        print(f"  answer: {' '.join(r['answer'].split())[:400]}")
    print(f"\nwrote {RESULTS_JSON.name} and {RESULTS_MD.name}")
    return 0


def _write_md(summary: dict, results: list[dict]) -> None:
    lines = [
        "# Eval results",
        "",
        f"- answer model: `{summary['answer_model']}`  |  judge model: "
        f"`{summary['judge_model']}`  |  k = {summary['k']}",
        f"- **judge pass rate: {summary['judge_pass']}/{summary['n_questions']} "
        f"({summary['judge_pass_rate']:.0%})**  "
        f"(borderline {summary['judge_borderline']}, fail {summary['judge_fail']})",
        f"- **retrieval recall: {summary['retrieval_recall_hits']}/"
        f"{summary['retrieval_scored']} ({summary['retrieval_recall_rate']:.0%})**  "
        f"(scored questions only)",
        "",
        "Recall is measured at *section* granularity. For a split section a hit here "
        "does not guarantee the specific sub-chunk carrying the answer was retrieved "
        "(see q10: §5.2 hit at rank 8, but the retrieved chunk was 5.2/6, not the "
        "5.2/3 that holds the surgery criterion - the bot correctly deferred).",
        "",
        "| id | category | behaviour | judge | retrieval | citations |",
        "|----|----------|-----------|-------|-----------|-----------|",
    ]
    for r in results:
        rec = r["retrieval"]
        if not rec["checked"]:
            rcell = "n/a"
        elif rec["found"]:
            rcell = f"rank {rec['first_rank']}"
            if rec["n_expected_total"] > 1:
                rcell += f" ({rec['n_expected_found']}/{rec['n_expected_total']})"
        else:
            rcell = "**MISS**"
        cites = ", ".join(f"§{c['section_number']}" for c in r["citations"]) or "none"
        v = r["judge"]["verdict"]
        vcell = {"pass": "pass", "fail": "**FAIL**", "borderline": "_borderline_"}.get(v, v)
        lines.append(f"| {r['id']} | {r['category']} | {r['expected_behavior']} | "
                     f"{vcell} | {rcell} | {cites} |")

    lines += ["", "## Per-question detail", ""]
    for r in results:
        lines += [
            f"### {r['id']} — {r['question']}",
            f"*expected: {r['expected_behavior']}"
            + (f" (also acceptable: {', '.join(r['also_acceptable'])})" if r["also_acceptable"] else "")
            + f" · judge: **{r['judge']['verdict']}***",
            "",
            f"> {r['judge']['reasoning']}",
            "",
            f"- retrieval: expected `{r['retrieval']['expected_sections']}`, "
            f"top-8 `{r['retrieval']['retrieved_sections']}`"
            + (f", first hit at rank {r['retrieval']['first_rank']}" if r["retrieval"]["found"] else ", **no expected section retrieved**"),
            f"- citations parsed: {r['citations']}",
            "",
            "```",
            r["answer"],
            "```",
            "",
        ]
    RESULTS_MD.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

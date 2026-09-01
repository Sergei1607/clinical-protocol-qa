"""
Scoped table recovery for the two protocol sections that matter most for Q&A and
that PyMuPDF's plain-text pass flattened into noise:

  - 1.1  Synopsis                               (printed pages 15-18)
  - 3    Hypotheses, Objectives, and Endpoints  (printed pages 42-43)

Strategy: re-read just those page ranges with pdfplumber, pull the real table
grids with find_tables(), render them as Markdown tables, and interleave them
(by vertical position) with the non-table prose on the same pages. This is NOT a
general table parser - it is hard-coded to these two ranges.

Output: data/extracted/recovered_sections.json  - consumed by build_chunks.py,
which overrides the (excluded) 1.1 / 3 records from sections.json with these.

Run from backend/ :  python recover_tables.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pdfplumber

REPO_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = REPO_ROOT / "data" / "raw" / "Prot_000.pdf"
OUT_PATH = REPO_ROOT / "data" / "extracted" / "recovered_sections.json"

REDACTION_MARKER = "[REDACTED: commercially confidential information]"

# printed page == pdfplumber page index (cover is index 0)
TARGETS = [
    {"section_number": "1.1", "title": "Synopsis",
     "breadcrumb": "1 PROTOCOL SUMMARY > 1.1 Synopsis",
     "level": 2, "pages": [15, 16, 17, 18]},
    {"section_number": "3", "title": "Hypotheses, Objectives, and Endpoints",
     "breadcrumb": "3 HYPOTHESES, OBJECTIVES, AND ENDPOINTS",
     "level": 1, "pages": [42, 43]},
]

FURNITURE_RE = re.compile(
    r"^(PRODUCT:\s*MK-6482.*|PROTOCOL/AMENDMENT\s*NO\.:.*"
    r"|MK-6482-005-09\s*FINAL\s*PROTOCOL.*|14-NOV-2024|08RD3B|\d{1,3})$")
HEADING_RE = re.compile(r"^\d+(\.\d+){0,3}\s+[A-Z]")

# pdfminer drops a few inter-word spaces on tightly-kerned runs in this PDF;
# fixed here for the scoped recovery (documented, not silent).
KNOWN_SPACING_FIXES = {"amultisitestudy": "a multisite study"}


def fix_spacing(s: str) -> str:
    s = re.sub(r"([a-z]):([A-Z0-9])", r"\1: \2", s)      # "Title:An" -> "Title: An"
    s = re.sub(r"([A-Za-z])-\s+([A-Za-z0-9])", r"\1-\2", s)  # "PD- 1/L1" -> "PD-1/L1"
    for bad, good in KNOWN_SPACING_FIXES.items():
        s = s.replace(bad, good)
    return s


def render_table(tbl) -> str:
    rows = [[" ".join((c or "").split()) for c in r] for r in tbl.extract()]
    rows = [r for r in rows if any(cell for cell in r)]
    if not rows:
        return ""
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    rows = [[REDACTION_MARKER if c == "CCI" else fix_spacing(c) for c in r]
            for r in rows]
    md = ["| " + " | ".join(rows[0]) + " |",
          "| " + " | ".join(["---"] * ncol) + " |"]
    for r in rows[1:]:
        md.append("| " + " | ".join(r) + " |")
    return "\n".join(md)


def page_blocks(page):
    """Yield (top_y, kind, text) for every table and every prose line on a page,
    with running headers/footers and the section heading line removed."""
    tables = page.find_tables()
    boxes = [t.bbox for t in tables]
    for t in tables:
        rendered = render_table(t)
        if rendered:
            yield (t.bbox[1], "table", rendered)

    def outside_tables(obj):
        cx = (obj["x0"] + obj["x1"]) / 2
        cy = (obj["top"] + obj["bottom"]) / 2
        return not any(x0 <= cx <= x1 and y0 <= cy <= y1 for x0, y0, x1, y1 in boxes)

    for line in page.filter(outside_tables).extract_text_lines(layout=False):
        s = " ".join(line["text"].split())
        if not s or FURNITURE_RE.match(s) or HEADING_RE.match(s):
            continue
        s = REDACTION_MARKER if s == "CCI" else fix_spacing(s)
        yield (line["top"], "prose", s)


def assemble(blocks: list[tuple]) -> str:
    """blocks already in reading order: list of (kind, text)."""
    out: list[str] = []
    prose_buf: list[str] = []

    def flush_prose():
        if not prose_buf:
            return
        joined: list[str] = []
        for s in prose_buf:
            if joined and re.search(r"[A-Za-z]-$", joined[-1]):
                joined[-1] = joined[-1][:-1] + "-" + s          # PD-\n1/L1 -> PD-1/L1
            elif joined and not re.search(r"[.:;?!]$", joined[-1]) \
                    and not joined[-1].endswith(REDACTION_MARKER) \
                    and not s[:1].isupper():
                joined[-1] += " " + s
            else:
                joined.append(s)
        out.append("\n".join(joined))
        prose_buf.clear()

    for kind, text in blocks:
        if kind == "prose":
            prose_buf.append(text)
        else:
            flush_prose()
            out.append(text)
    flush_prose()
    return "\n\n".join(out).strip()


def recover_one(pdf, target: dict) -> dict:
    ordered: list[tuple] = []
    for pno in target["pages"]:
        page = pdf.pages[pno]
        for top, kind, text in sorted(page_blocks(page), key=lambda b: b[0]):
            ordered.append((kind, text))
    text = assemble(ordered)
    return {
        "section_number": target["section_number"],
        "title": target["title"],
        "breadcrumb": target["breadcrumb"],
        "level": target["level"],
        "start_page": target["pages"][0],
        "end_page": target["pages"][-1],
        "char_count": len(text),
        "recovered_via": "pdfplumber find_tables()",
        "has_partial_redaction": REDACTION_MARKER in text,
        "text": text,
    }


def main() -> int:
    with pdfplumber.open(PDF_PATH) as pdf:
        recovered = [recover_one(pdf, t) for t in TARGETS]
    OUT_PATH.write_text(json.dumps(recovered, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    for r in recovered:
        print(f"\n{'=' * 78}\n{r['section_number']}  {r['title']}  "
              f"({r['char_count']} chars, pages {r['start_page']}-{r['end_page']}, "
              f"partial_redaction={r['has_partial_redaction']})\n{'=' * 78}")
        print(r["text"])
    print(f"\nWrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

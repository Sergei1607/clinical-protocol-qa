"""
Step 2 of the pipeline: turn the flat extracted protocol text into structured,
section-boundary records ready for (later) sub-chunking and embedding.

Pipeline:
  1. Clean each page  - strip the 5-line running header + "08RD3B" footer,
     collapse stacked "CCI" redaction tokens to one marker.
  2. Parse the Table of Contents (printed pages 7-13) into an ordered
     section-number -> (title, printed page) map, noting dot-leader-only
     entries that mark a redacted-away section.
  3. Walk the body text, detecting headings ("<number>" alone on a line, title
     on the next), cross-checking each against the TOC title so stray numbers
     in prose don't register as headings.
  4. Cross-validate TOC vs body and collect every discrepancy (no silent fixes).
  5. Build the section tree; for every leaf section (and every non-leaf section
     that has its own preamble text) emit a record with breadcrumb, page span,
     cleaned text, char count, and is_redacted / is_flattened_table flags.
  6. Write data/extracted/sections.json and print a full report.

Excluded up front by decision (see CLAUDE.md / last session):
  - printed pages 3-6  (Document History, Amendment Summary of Changes)
  - printed pages 7-15 (TOC, List of Tables, List of Figures) - parsed only
  - any section detected as a badly-flattened multi-column table

Run from backend/ :  python parse_sections.py
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTED = REPO_ROOT / "data" / "extracted" / "protocol_text.txt"
SECTIONS_JSON = REPO_ROOT / "data" / "extracted" / "sections.json"

# --- fixed document facts, established by inspection ------------------------
RUNNING_HEADER_FIRST_LINE = "PRODUCT: MK-6482"
RUNNING_HEADER_LEN = 5          # PRODUCT / <printed no.> / PROTOCOL-AMENDMENT / MK-6482-005-09 FINAL / 14-NOV-2024
RUNNING_FOOTER = "08RD3B"
REDACTION_TOKEN = "CCI"
REDACTION_MARKER = "[REDACTED: commercially confidential information]"
# printed page N  ==  pages[N]   (cover is pages[0], unnumbered; printed 1 is pages[1])
PRINTED_TO_INDEX_OFFSET = 0
BODY_START_PRINTED = 15         # section 1 "PROTOCOL SUMMARY" begins here
TOC_PRINTED_PAGES = range(6, 13)  # 6..12 hold the numbered TOC (13/14 = tables/figures)

BULLET_CHARS = "•◦●‣⁃∙"  # • (Symbol) ◦ ● ‣ ⁃ ∙

NUM_RE = re.compile(r"^\d+(?:\.\d+){0,3}$")
# a TOC title line ends with <text> <dot-leader> <page number>. The leader is
# usually many dots but occasionally a single " ." - so require >=1 dot and a
# title that ends on a real (non-dot, non-space) character.
TOC_PAGENUM_RE = re.compile(r"^(?P<title>.*?[^\s.])\s*\.+\s*(?P<page>\d{1,3})\s*$")
TOC_DOTLEADER_ONLY_RE = re.compile(r"^[.\s]*\.{2,}\s*(?:\d+)?\s*$")


# ==========================================================================
# 1. load + clean pages
# ==========================================================================
def load_pages() -> list[str]:
    return EXTRACTED.read_text(encoding="utf-8").split("\f")


def page_printed_number(raw_page: str) -> int | None:
    lines = raw_page.splitlines()
    if lines and lines[0].strip() == RUNNING_HEADER_FIRST_LINE and len(lines) > 1:
        m = re.fullmatch(r"\d+", lines[1].strip())
        if m:
            return int(lines[1].strip())
    return None


def strip_running_furniture(raw_page: str) -> list[str]:
    """Drop the running header block and the trailing footer watermark.

    Trailing "CCI" lines are left in place - they mark a redacted figure/table
    that belonged to this page's section, and collapse_redactions() turns them
    into an attributable marker.
    """
    lines = raw_page.splitlines()
    if lines and lines[0].strip() == RUNNING_HEADER_FIRST_LINE:
        lines = lines[RUNNING_HEADER_LEN:]
    while lines and (not lines[-1].strip() or lines[-1].strip() == RUNNING_FOOTER):
        lines.pop()
    return lines


def collapse_redactions(lines: list[str]) -> list[str]:
    """Replace any run of stacked bare 'CCI' lines with a single marker line."""
    out: list[str] = []
    run = 0
    for ln in lines:
        if ln.strip() == REDACTION_TOKEN:
            run += 1
            continue
        if run:
            out.append(REDACTION_MARKER)
            run = 0
        out.append(ln)
    if run:
        out.append(REDACTION_MARKER)
    return out


# ==========================================================================
# 2. parse the table of contents
# ==========================================================================
def parse_toc(pages: list[str]) -> tuple[list[dict], list[dict]]:
    """Return (entries, redacted_markers).

    entries: [{number, title, page}] in document order.
    redacted_markers: [{page, after_number}] for dot-leader-only TOC lines
    (a section whose number and title were redacted away).
    """
    lines: list[str] = []
    for printed in TOC_PRINTED_PAGES:
        lines += strip_running_furniture(pages[printed + PRINTED_TO_INDEX_OFFSET])

    entries: list[dict] = []
    redacted: list[dict] = []
    last_number = None
    i = 0
    while i < len(lines):
        ln = lines[i].strip()
        if not ln:
            i += 1
            continue
        if ln.upper() in ("TABLE OF CONTENTS",):
            i += 1
            continue
        if ln.upper().startswith(("LIST OF TABLES", "LIST OF FIGURES")):
            break

        if NUM_RE.fullmatch(ln):
            number = ln
            # gather title lines until one carries the page number
            title_parts: list[str] = []
            page = None
            j = i + 1
            while j < len(lines) and j < i + 5:
                cand = lines[j].strip()
                m = TOC_PAGENUM_RE.match(cand)
                if m:
                    if m.group("title").strip():
                        title_parts.append(m.group("title").strip())
                    page = int(m.group("page"))
                    j += 1
                    break
                if cand and not NUM_RE.fullmatch(cand):
                    title_parts.append(cand)
                    j += 1
                else:
                    break
            title = re.sub(r"\s+", " ", " ".join(title_parts)).strip(" .")
            entries.append({"number": number, "title": title, "page": page})
            last_number = number
            i = j
            continue

        if TOC_DOTLEADER_ONLY_RE.match(ln):
            pm = re.search(r"(\d+)\s*$", ln)
            redacted.append({"page": int(pm.group(1)) if pm else None,
                             "after_number": last_number})
            i += 1
            continue

        # front-matter TOC lines like "DOCUMENT HISTORY .... 3" - ignore
        i += 1

    return entries, redacted


# ==========================================================================
# 3. build the cleaned body line list + detect headings
# ==========================================================================
def build_body_lines(pages: list[str]) -> tuple[list[dict], list[int]]:
    """Flat list of {idx, printed, text} for every cleaned body line, plus the
    list of printed page numbers that are 100% redaction after cleaning."""
    body: list[dict] = []
    fully_redacted: list[int] = []
    for pdf_idx, raw in enumerate(pages):
        printed = page_printed_number(raw)
        if printed is None or printed < BODY_START_PRINTED:
            continue
        lines = collapse_redactions(strip_running_furniture(raw))
        non_empty = [l for l in lines if l.strip()]
        if non_empty and all(l.strip() == REDACTION_MARKER for l in non_empty):
            fully_redacted.append(printed)
        for ln in lines:
            body.append({"idx": pdf_idx, "printed": printed, "text": ln})
    return body, fully_redacted


def _title_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def detect_headings(body: list[dict], toc_entries: list[dict]) -> tuple[list[dict], list[dict]]:
    """Find heading positions in the body.

    Returns (headings, extra) where headings align to toc_entries that were
    located, and extra are heading-like spots whose number is not in the TOC.
    """
    toc_by_num = {e["number"]: e for e in toc_entries}
    toc_numbers_in_order = [e["number"] for e in toc_entries]

    headings: list[dict] = []
    extra: list[dict] = []
    used_positions: set[int] = set()

    # search TOC entries in order, each starting after the previous match
    search_from = 0
    for entry in toc_entries:
        num = entry["number"]
        want = _title_key(entry["title"])[:14]
        found_at = None
        for k in range(search_from, len(body)):
            if body[k]["text"].strip() != num:
                continue
            # concat next up-to-3 non-empty lines as the candidate title
            nxt = []
            kk = k + 1
            while kk < len(body) and len(nxt) < 3:
                t = body[kk]["text"].strip()
                if t:
                    nxt.append(t)
                kk += 1
            cand = _title_key(" ".join(nxt))
            if want and cand.startswith(want[:8]):
                found_at = k
                break
        if found_at is not None:
            headings.append({
                "number": num,
                "title": entry["title"],
                "toc_page": entry["page"],
                "body_pos": found_at,
                "printed": body[found_at]["printed"],
                "pdf_idx": body[found_at]["idx"],
            })
            used_positions.add(found_at)
            search_from = found_at + 1
        else:
            headings.append({
                "number": num,
                "title": entry["title"],
                "toc_page": entry["page"],
                "body_pos": None,
                "printed": None,
                "pdf_idx": None,
            })

    # scan for heading-like numbers that are NOT in the TOC
    for k, row in enumerate(body):
        t = row["text"].strip()
        if not NUM_RE.fullmatch(t) or t in toc_by_num:
            continue
        # next non-empty line looks like a title (starts uppercase, some letters)
        nxt = ""
        for kk in range(k + 1, min(k + 3, len(body))):
            if body[kk]["text"].strip():
                nxt = body[kk]["text"].strip()
                break
        if nxt[:1].isupper() and len(re.findall(r"[A-Za-z]", nxt)) >= 4 and len(nxt) < 90:
            # avoid list items like "8." (those keep text on the same line, so
            # they never reach here) and numeric table cells (no title-ish next)
            extra.append({"number": t, "next_line": nxt,
                          "printed": row["printed"], "body_pos": k})

    return headings, extra


# ==========================================================================
# 4. text cleaning for a section body
# ==========================================================================
def normalise_bullets(text: str) -> str:
    text = re.sub(rf"[{BULLET_CHARS}]\s*", "• ", text)
    return text


LONE_BULLET_RE = re.compile(rf"^[{re.escape(BULLET_CHARS)}\-–—]$")
LIST_ITEM_RE = re.compile(r"^(\d{1,2}[.)]|[a-z][.)]|[ivx]{1,4}[.)])\s")


def _prenormalise(raw_lines: list[str]) -> list[str]:
    """Fold lone bullet-marker lines into the line they introduce, so the join
    pass sees one '• text' line instead of '-' \\n 'text'."""
    out: list[str] = []
    pending_bullet = False
    for ln in raw_lines:
        s = ln.strip()
        if not s:
            out.append("")
            pending_bullet = False
            continue
        if LONE_BULLET_RE.match(s):
            pending_bullet = True
            continue
        if pending_bullet:
            out.append("• " + s)
            pending_bullet = False
        else:
            out.append(s)
    return out


def clean_section_text(raw_lines: list[str]) -> str:
    lines = _prenormalise(raw_lines)
    parts: list[str] = []
    for s in lines:
        if not s:
            if parts and parts[-1] != "":
                parts.append("")
            continue
        cur = s.strip()
        if not parts or parts[-1] == "":
            parts.append(cur)
            continue
        prev = parts[-1]
        cur_is_bullet = cur[:1] in BULLET_CHARS or cur.startswith("• ")
        cur_is_listitem = bool(LIST_ITEM_RE.match(cur))
        if re.search(r"[A-Za-z]-$", prev) and re.match(r"[A-Za-z0-9]", cur):
            parts[-1] = prev[:-1] + "-" + cur           # follow-up, PD-1/L1, VEGF-TKI
        elif prev.endswith("-") and re.match(r"[A-Za-z0-9]", cur):
            parts[-1] = prev + cur
        elif (cur_is_bullet or cur_is_listitem
                or re.search(r"[.:;?!]['\"”]?$", prev)
                or prev.endswith(REDACTION_MARKER)):
            parts.append(cur)
        else:
            parts[-1] = prev + " " + cur

    text = "\n".join(parts)
    text = normalise_bullets(text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fragmentation_ratio(raw_lines: list[str]) -> float:
    real = [l.strip() for l in raw_lines if l.strip()]
    if not real:
        return 0.0
    frag = sum(1 for l in real
               if len(l) < 40 and not l.endswith((".", ":", ";", ")", ","))
               and l != REDACTION_MARKER)
    return frag / len(real)


SOA_MINI_HEADER = ["Study Period", "Screening", "Treatment Period", "EOT",
                   "Posttreatment", "Notes"]


def looks_like_flattened_table(number: str, raw_lines: list[str]) -> tuple[bool, str]:
    real = [l.strip() for l in raw_lines if l.strip()]
    if number == "1.3":
        return True, "Schedule of Activities matrix (decided exclusion)"
    joined_head = " ".join(real[:8])
    if sum(h in joined_head for h in SOA_MINI_HEADER) >= 4:
        return True, "repeating Schedule-of-Activities column header"
    if len(real) >= 15 and fragmentation_ratio(raw_lines) >= 0.55:
        return True, f"{fragmentation_ratio(raw_lines):.0%} short fragmented lines"
    return False, ""


# ==========================================================================
# 5. assemble section records
# ==========================================================================
def parent_number(num: str) -> str | None:
    return num.rsplit(".", 1)[0] if "." in num else None


def build_records(headings: list[dict], body: list[dict],
                  fully_redacted_pages: list[int]) -> list[dict]:
    fr = set(fully_redacted_pages)
    located = [h for h in headings if h["body_pos"] is not None]
    located.sort(key=lambda h: h["body_pos"])
    by_num = {h["number"]: h for h in located}
    all_numbers = {h["number"] for h in headings}

    def is_leaf(num: str) -> bool:
        return not any(other != num and other.startswith(num + ".")
                       for other in all_numbers)

    def breadcrumb(num: str) -> str:
        chain = []
        cur = num
        while cur is not None:
            h = by_num.get(cur)
            label = f"{cur} {h['title']}" if h else cur
            chain.append(label)
            cur = parent_number(cur)
        return " > ".join(reversed(chain))

    records: list[dict] = []
    for pos, h in enumerate(located):
        num = h["number"]
        start = h["body_pos"]
        end = located[pos + 1]["body_pos"] if pos + 1 < len(located) else len(body)

        # split into "preamble" (before first child heading) and child span
        child_positions = [o["body_pos"] for o in located[pos + 1:]
                           if (o["number"].startswith(num + ".")
                               and o["number"].count(".") == num.count(".") + 1)]
        first_child = min(child_positions) if child_positions else end
        preamble_lines = [body[k]["text"] for k in range(start + 2, first_child)]

        leaf = is_leaf(num)
        if leaf:
            raw_lines = [body[k]["text"] for k in range(start + 2, end)]
            span_positions = list(range(start, end))
        else:
            raw_lines = preamble_lines
            span_positions = list(range(start, first_child))

        if not leaf and len("".join(l.strip() for l in raw_lines)) < 60:
            continue  # non-leaf with no real preamble - skip, children carry it

        # trim trailing fully-redacted pages: they are a redaction gap before the
        # next heading, not this section's content (e.g. 10.7.5 -> pp.142-147)
        trailing_redacted: list[int] = []
        while span_positions and body[span_positions[-1]]["printed"] in fr:
            pg = body[span_positions[-1]]["printed"]
            if pg not in trailing_redacted:
                trailing_redacted.insert(0, pg)
            span_positions.pop()
        if trailing_redacted:
            keep = set(span_positions)
            raw_lines = [body[k]["text"] for k in range(start + 2, (end if leaf else first_child))
                         if k in keep]

        pages_in_span = [body[k]["printed"] for k in span_positions]
        start_page = min(pages_in_span) if pages_in_span else h["printed"]
        end_page = max(pages_in_span) if pages_in_span else h["printed"]

        text = clean_section_text(raw_lines)
        if leaf and not text.strip():
            text = REDACTION_MARKER + " (heading present in body; no content - redacted or relocated)"
        without_marker = text.replace(REDACTION_MARKER, "").strip()
        n_markers = text.count(REDACTION_MARKER)
        # is_redacted  = wholly or mostly gone: a CCI marker with almost no prose
        #                left, or a heading with no body at all.
        # partial_redaction = has real prose but also lost a figure/table to CCI;
        #                still retrievable, just flagged.
        is_redacted = n_markers > 0 and len(without_marker) < 150
        has_partial_redaction = n_markers > 0 and not is_redacted

        is_table, table_reason = looks_like_flattened_table(num, raw_lines)
        # rough measure of how much readable prose a flagged table still holds
        prose_chars = sum(len(l.strip()) for l in raw_lines
                          if len(l.strip()) >= 60 and l.strip().endswith((".", ":", ";")))

        records.append({
            "section_number": num,
            "title": h["title"],
            "breadcrumb": breadcrumb(num),
            "level": num.count(".") + 1,
            "is_leaf": leaf,
            "is_section_preamble": not leaf,
            "start_page": start_page,
            "end_page": end_page,
            "char_count": len(text),
            "is_redacted": bool(is_redacted),
            "has_partial_redaction": bool(has_partial_redaction),
            "is_flattened_table": bool(is_table),
            "flattened_table_reason": table_reason or None,
            "flattened_table_prose_chars": prose_chars if is_table else None,
            "trailing_redacted_pages": trailing_redacted or None,
            "excluded_from_retrieval": bool(is_redacted or is_table),
            "exclusion_reason": ("redacted" if is_redacted
                                 else "flattened_table" if is_table else None),
            "text": text,
        })
    return records


# ==========================================================================
# 6. report
# ==========================================================================
def pct(values: list[int], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def report(toc_entries, toc_redacted, headings, extra, records, fully_redacted_pages):
    print("=" * 74)
    print("SECTION PARSE REPORT")
    print("=" * 74)

    located = [h for h in headings if h["body_pos"] is not None]
    missing = [h for h in headings if h["body_pos"] is None]
    print(f"TOC entries parsed:                 {len(toc_entries)}")
    print(f"TOC dot-leader-only (redacted):     {len(toc_redacted)}")
    print(f"Headings located in body text:      {len(located)}")
    print(f"TOC entries NOT found in body:      {len(missing)}")
    print(f"Heading-like numbers not in TOC:    {len(extra)}")
    print(f"Section records emitted:            {len(records)}")
    leaves = [r for r in records if r['is_leaf']]
    preambles = [r for r in records if not r['is_leaf']]
    print(f"   leaf sections:                   {len(leaves)}")
    print(f"   non-leaf preamble records:       {len(preambles)}")

    redacted = [r for r in records if r["is_redacted"]]
    partial = [r for r in records if r["has_partial_redaction"]]
    tables = [r for r in records if r["is_flattened_table"]]
    print(f"\nFlagged is_redacted (excluded):     {len(redacted)}")
    for r in redacted:
        print(f"   {r['section_number']:<10} p{r['start_page']:<4} {r['title'][:58]}")
    print(f"\nhas_partial_redaction (kept):       {len(partial)}")
    for r in partial:
        print(f"   {r['section_number']:<10} p{r['start_page']:<4} {r['char_count']:>5} chars  {r['title'][:50]}")
    print(f"\nFlagged is_flattened_table:         {len(tables)}")
    print(f"   {'section':<10} {'pages':<10} {'chars':>6} {'prose':>6}  title / reason")
    for r in tables:
        pr = r["flattened_table_prose_chars"] or 0
        tag = "  <- still has prose, revisit" if pr > 500 else ""
        print(f"   {r['section_number']:<10} p{r['start_page']}-{r['end_page']:<7} "
              f"{r['char_count']:>6} {pr:>6}  {r['title'][:40]}{tag}")
        print(f"   {'':<10} {'':<10} {'':>6} {'':>6}  reason: {r['flattened_table_reason']}")

    print("\n" + "-" * 74)
    print("TOC vs BODY DISCREPANCIES (no silent fixes - review together)")
    print("-" * 74)
    n = 0
    for h in missing:
        n += 1
        print(f"  [{n}] TOC {h['number']!r} ({h['title'][:50]!r}) - no heading found in body")
    for m in toc_redacted:
        n += 1
        print(f"  [{n}] TOC redacted entry: dot-leader only, page {m['page']}, "
              f"after section {m['after_number']}")
    for e in extra:
        n += 1
        print(f"  [{n}] body heading {e['number']!r} + {e['next_line'][:45]!r} "
              f"(p{e['printed']}) - not in TOC")
    # page-order sanity: located headings should be monotonic by printed page
    prev = 0
    for h in sorted(located, key=lambda x: x["body_pos"]):
        if h["printed"] < prev:
            n += 1
            print(f"  [{n}] {h['number']} heading on p{h['printed']} follows a later page "
                  f"(page numbers out of order)")
        prev = max(prev, h["printed"])
    # TOC page vs detected page mismatch > 1
    for h in located:
        if h["toc_page"] is not None and abs(h["toc_page"] - h["printed"]) > 1:
            n += 1
            print(f"  [{n}] {h['number']} TOC says p{h['toc_page']} but heading found on "
                  f"p{h['printed']}")
    if n == 0:
        print("  (none)")

    print("\n" + "-" * 74)
    print("SECTION LENGTH STATISTICS (character count of cleaned text)")
    print("-" * 74)
    def stats(label, rs):
        cs = [r["char_count"] for r in rs]
        if not cs:
            print(f"  {label}: (no sections)")
            return
        print(f"  {label}  (n={len(cs)})")
        print(f"     min {min(cs):>6}   p25 {pct(cs,.25):>8.0f}   median {statistics.median(cs):>8.0f}"
              f"   p75 {pct(cs,.75):>8.0f}   max {max(cs):>7}")
    stats("all leaf + preamble records ", records)
    stats("retrievable only (not excl.)", [r for r in records if not r["excluded_from_retrieval"]])
    stats("excluded (redacted/table)   ", [r for r in records if r["excluded_from_retrieval"]])

    retr = [r for r in records if not r["excluded_from_retrieval"]]
    long_rs = sorted(retr, key=lambda r: -r["char_count"])[:12]
    print("\n  longest retrievable sections (candidates for sub-chunking next):")
    for r in long_rs:
        print(f"     {r['char_count']:>6}  {r['section_number']:<10} {r['title'][:52]}")
    tiny = sorted((r for r in retr if r["char_count"] < 120), key=lambda r: r["char_count"])
    print(f"\n  very short retrievable sections (<120 chars, n={len(tiny)}) "
          f"- candidates to merge with parent:")
    for r in tiny:
        print(f"     {r['char_count']:>6}  {r['section_number']:<10} {r['title'][:44]}")

    print("\n" + "-" * 74)
    print(f"FULLY-REDACTED PAGES (100% CCI after cleaning): {len(fully_redacted_pages)}")
    print("-" * 74)
    print(f"  printed pages: {fully_redacted_pages}")
    print("  -> content that lived only on these pages is unrecoverable; this")
    print("     explains missing body headings for redacted TOC entries.")
    print("\n" + "-" * 74)
    print("JUDGMENT CALLS TO CONFIRM TOGETHER")
    print("-" * 74)
    print("  - Section 11 REFERENCES is kept retrievable but is a fragmented")
    print("    bibliography, not Q&A content - exclude it?")
    print("  - 1.1 Synopsis and 3 Hypotheses/Objectives/Endpoints are flagged as")
    print("    flattened tables (~56%) but hold high-value summary content -")
    print("    rescue via a dedicated parser, or accept the loss for v1?")
    print("  - 6.1 / 6.6.1 / 8.4.1 / 10.2 are mixed prose+table: excluded now,")
    print("    but each still carries 150-700 chars of real prose.")
    print("  - 9.3 Hypotheses/Estimation is marked redacted+excluded: only a")
    print("    'stated in Section 3' pointer survives; the estimands text is CCI.")

    span_rs = [r for r in records if r["end_page"] - r["start_page"] >= 6]
    if span_rs:
        print("\n  sections spanning >=6 printed pages (check for swallowed subsections):")
        for r in span_rs:
            tr = r["trailing_redacted_pages"]
            print(f"     {r['section_number']:<10} p{r['start_page']}-{r['end_page']}  "
                  f"{r['title'][:40]}" + (f"   (trimmed redacted tail {tr})" if tr else ""))


# ==========================================================================
def main() -> int:
    pages = load_pages()
    toc_entries, toc_redacted = parse_toc(pages)
    body, fully_redacted = build_body_lines(pages)
    headings, extra = detect_headings(body, toc_entries)
    records = build_records(headings, body, fully_redacted)

    payload = {
        "source": "data/extracted/protocol_text.txt",
        "protocol": "MK-6482-005 / NCT04195750",
        "counts": {
            "toc_entries": len(toc_entries),
            "toc_redacted_markers": len(toc_redacted),
            "headings_located": sum(1 for h in headings if h["body_pos"] is not None),
            "records": len(records),
            "leaf": sum(1 for r in records if r["is_leaf"]),
            "preamble": sum(1 for r in records if not r["is_leaf"]),
            "redacted": sum(1 for r in records if r["is_redacted"]),
            "partial_redaction": sum(1 for r in records if r["has_partial_redaction"]),
            "flattened_table": sum(1 for r in records if r["is_flattened_table"]),
            "retrievable": sum(1 for r in records if not r["excluded_from_retrieval"]),
        },
        "fully_redacted_printed_pages": fully_redacted,
        "toc_redacted_markers": toc_redacted,
        "sections": records,
    }
    SECTIONS_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                             encoding="utf-8")
    report(toc_entries, toc_redacted, headings, extra, records, fully_redacted)
    print(f"\nWrote {SECTIONS_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

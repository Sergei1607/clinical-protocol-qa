"""
Step 3 of the pipeline: turn the section-level records in sections.json into the
final retrieval chunk set, data/extracted/chunks.json.

Transforms applied (sections.json is NOT modified - it stays the source of truth):
  1. Override 1.1 Synopsis and 3 Hypotheses/Objectives/Endpoints with the
     pdfplumber-recovered versions from recovered_sections.json, and mark them
     retrievable again.
  2. Exclude section 11 REFERENCES (exclusion_reason "non-qa-content").
  3. Merge each short (<~150 char) leaf section in MERGE_INTO_PARENT into its
     immediate parent's chunk; if the parent has no record of its own, create a
     chunk under the parent's breadcrumb.
  4. Split every retrievable section longer than SPLIT_MIN_CHARS into sub-chunks,
     preferring numbered-list-item > sub-bullet > paragraph > sentence
     boundaries, never cutting mid-item and never splitting a Markdown table.
     Repeat the breadcrumb + a "[i/n]" index at the head of each sub-chunk and
     carry ~1 sentence of overlap from the previous sub-chunk.

Run from backend/ :  python build_chunks.py   (run recover_tables.py first)
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SECTIONS_JSON = REPO_ROOT / "data" / "extracted" / "sections.json"
RECOVERED_JSON = REPO_ROOT / "data" / "extracted" / "recovered_sections.json"
CHUNKS_JSON = REPO_ROOT / "data" / "extracted" / "chunks.json"

REDACTION_MARKER = "[REDACTED: commercially confidential information]"

# short leaf sections to fold into their immediate parent
MERGE_INTO_PARENT = ["6.9.1", "9.6.3", "8.1.10", "6.7", "10.4.1", "4.3.2",
                     "5.5", "8.1.8.2", "8.11", "8.1.5.2", "6.5.2"]

SPLIT_MIN_CHARS = 1800     # sections at/under this stay a single chunk
SUBCHUNK_TARGET = 1200     # aim for sub-chunk BODY around here (excl. breadcrumb + overlap)
SUBCHUNK_MAX = 1500        # soft body ceiling; a single atomic block may exceed it
SEGMENT_SENTENCE_SPLIT = 1700  # a non-table segment bigger than this is sentence-split
KEEP_ADDING_BELOW = 550    # keep growing a sub-chunk past target until at least this big
OVERLAP_CAP = 220

LIST_ITEM_RE = re.compile(r"^(\d{1,2}[.)]|[A-Za-z][.)]|[IVXLivxl]{1,4}[.)])\s")


# ==========================================================================
# load + pre-transform section records
# ==========================================================================
def load_records() -> list[dict]:
    sections = json.loads(SECTIONS_JSON.read_text(encoding="utf-8"))["sections"]
    by_num = {r["section_number"]: r for r in sections}

    # 1. recovered Synopsis / Section 3
    if RECOVERED_JSON.exists():
        for rec in json.loads(RECOVERED_JSON.read_text(encoding="utf-8")):
            n = rec["section_number"]
            tgt = by_num.get(n)
            if not tgt:
                continue
            tgt.update({
                "title": rec["title"],
                "text": rec["text"],
                "char_count": len(rec["text"]),
                "start_page": rec["start_page"],
                "end_page": rec["end_page"],
                "is_flattened_table": False,
                "flattened_table_reason": None,
                "has_partial_redaction": rec["has_partial_redaction"],
                "excluded_from_retrieval": False,
                "exclusion_reason": None,
                "recovered_via": rec["recovered_via"],
            })

    # 2. drop REFERENCES
    if "11" in by_num:
        by_num["11"]["excluded_from_retrieval"] = True
        by_num["11"]["exclusion_reason"] = "non-qa-content"

    return sections, by_num


def parent_number(num: str) -> str | None:
    return num.rsplit(".", 1)[0] if "." in num else None


def parent_meta(child: dict) -> tuple[str, str]:
    """(title, breadcrumb) for the child's immediate parent, from its breadcrumb."""
    crumbs = child["breadcrumb"].split(" > ")
    parent_crumb = " > ".join(crumbs[:-1])
    parent_title = crumbs[-2].split(" ", 1)[1] if len(crumbs) >= 2 and " " in crumbs[-2] else crumbs[-2]
    return parent_title, parent_crumb


# ==========================================================================
# 3. merge short sections
# ==========================================================================
def apply_merges(sections: list[dict], by_num: dict) -> tuple[list[dict], dict]:
    merged_log: dict[str, list[str]] = {}
    drop: set[str] = set()
    created: dict[str, dict] = {}

    for num in MERGE_INTO_PARENT:
        child = by_num.get(num)
        if not child or child["excluded_from_retrieval"]:
            continue
        pnum = parent_number(num) or num
        addition = f"\n\n{num} {child['title']}\n{child['text'].strip()}"
        target = by_num.get(pnum)
        if target and not target["excluded_from_retrieval"]:
            target["text"] = target["text"].rstrip() + addition
            target["char_count"] = len(target["text"])
            target["start_page"] = min(target["start_page"], child["start_page"])
            target["end_page"] = max(target["end_page"], child["end_page"])
            merged_log.setdefault(pnum, []).append(num)
        else:
            ptitle, pcrumb = parent_meta(child)
            if pnum not in created:
                created[pnum] = {
                    "section_number": pnum,
                    "title": ptitle,
                    "breadcrumb": pcrumb,
                    "level": pnum.count(".") + 1,
                    "is_leaf": False,
                    "is_section_preamble": True,
                    "start_page": child["start_page"],
                    "end_page": child["end_page"],
                    "text": "",
                    "has_partial_redaction": False,
                    "is_flattened_table": False,
                    "excluded_from_retrieval": False,
                    "exclusion_reason": None,
                }
            c = created[pnum]
            c["text"] = (c["text"].rstrip() + addition).strip()
            c["char_count"] = len(c["text"])
            c["start_page"] = min(c["start_page"], child["start_page"])
            c["end_page"] = max(c["end_page"], child["end_page"])
            c["has_partial_redaction"] |= child.get("has_partial_redaction", False)
            merged_log.setdefault(pnum + " (created)", []).append(num)
        drop.add(num)

    out = [r for r in sections if r["section_number"] not in drop]
    out.extend(created.values())
    return out, merged_log


# ==========================================================================
# 4. splitting
# ==========================================================================
def is_subheader(line: str) -> bool:
    s = line.strip()
    return (0 < len(s) <= 55 and not s.startswith(("•", "|"))
            and not s[:1].isdigit()
            and not s.endswith((".", ";", "!", "?"))
            and len(s.split()) <= 6 and s[:1].isupper())


CONTINUATION_RE = re.compile(r"^(Note:|Refer to |Examples of |measles,|http|OR$|[a-z])")


def _split_big_item(item: str) -> list[str]:
    """A single list item that is itself huge: break at Note:/Refer/sub-bullet."""
    lines = item.split("\n")
    out, cur = [], []
    for ln in lines:
        if cur and (ln.startswith(("• ", "Note:", "Refer to ")) and len("\n".join(cur)) > 600):
            out.append("\n".join(cur))
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        out.append("\n".join(cur))
    return out


def to_segments(text: str) -> list[str]:
    """Split section text into segments that must never be cut internally:
    a numbered/lettered list item keeps its Notes/sub-bullets; a Markdown table
    stays whole; every other line is its own segment (parse_sections already
    grouped wrapped prose into ~sentence lines). Sub-headers attach to the
    segment that follows them.
    """
    lines = text.split("\n")
    segs: list[str] = []
    pending_subheader = ""
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("|"):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            seg = "\n".join(lines[i:j]).strip()
            segs.append((pending_subheader + "\n" + seg).strip() if pending_subheader else seg)
            pending_subheader = ""
            i = j
            continue
        if not ln.strip():
            i += 1
            continue
        if is_subheader(ln):
            pending_subheader = (pending_subheader + "\n" + ln).strip()
            i += 1
            continue
        if LIST_ITEM_RE.match(ln):
            item = [ln]
            i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].startswith("|") \
                    and not LIST_ITEM_RE.match(lines[i]) and not is_subheader(lines[i]):
                item.append(lines[i])
                i += 1
            seg = "\n".join(item)
            parts = _split_big_item(seg) if len(seg) > SUBCHUNK_MAX else [seg]
            if pending_subheader:
                parts[0] = pending_subheader + "\n" + parts[0]
                pending_subheader = ""
            segs.extend(parts)
            continue
        seg = (pending_subheader + "\n" + ln).strip() if pending_subheader else ln
        pending_subheader = ""
        segs.append(seg)
        i += 1
    if pending_subheader:
        segs.append(pending_subheader)
    return segs


def sentence_split(seg: str) -> list[str]:
    parts = re.split(r"(?<=[.:;])\s+(?=[A-Z(•])", seg)
    out, buf = [], ""
    for p in parts:
        if buf and len(buf) + 1 + len(p) > SUBCHUNK_TARGET:
            out.append(buf)
            buf = p
        else:
            buf = f"{buf} {p}".strip()
    if buf:
        out.append(buf)
    return out or [seg]


def pack(segments: list[str]) -> list[str]:
    units: list[str] = []
    for seg in segments:
        if len(seg) > SEGMENT_SENTENCE_SPLIT and not seg.startswith("|"):
            units.extend(sentence_split(seg))
        else:
            units.append(seg)

    chunks: list[str] = []
    cur = ""
    for u in units:
        if not cur:
            cur = u
            continue
        joined_len = len(cur) + 2 + len(u)
        if joined_len <= SUBCHUNK_MAX or (len(cur) < KEEP_ADDING_BELOW and joined_len <= 1900):
            cur += "\n\n" + u
        else:
            chunks.append(cur)
            cur = u
    if cur:
        chunks.append(cur)

    # fold a small trailing remnant back into the previous chunk
    if len(chunks) >= 2 and len(chunks[-1]) < 400 and len(chunks[-2]) + len(chunks[-1]) <= 2000:
        remnant = chunks.pop()
        chunks[-1] += "\n\n" + remnant
    return chunks


def last_sentence(text: str) -> str:
    plain = "\n".join(l for l in text.splitlines() if not l.startswith("|")).strip()
    plain = re.sub(r"\s+", " ", plain)
    parts = [p for p in re.split(r"(?<=[.:;?!])\s+", plain) if p.strip()]
    if not parts:
        return ""
    tail = parts[-1]
    if len(tail) < 45 and len(parts) > 1:
        tail = parts[-2] + " " + tail
    tail = tail.strip()
    if len(tail) > OVERLAP_CAP:                    # keep the tail end, on a word boundary
        tail = tail[-OVERLAP_CAP:]
        tail = tail[tail.find(" ") + 1:] if " " in tail else tail
    return tail


# ==========================================================================
# build chunk records
# ==========================================================================
def chunk_records(rec: dict) -> list[dict]:
    base = {
        "section_number": rec["section_number"],
        "section_title": rec["title"],
        "breadcrumb": rec["breadcrumb"],
        "page_start": rec["start_page"],
        "page_end": rec["end_page"],
        "is_partial_redaction": bool(rec.get("has_partial_redaction")),
        "source": "pdfplumber" if rec.get("recovered_via") else "pymupdf",
    }
    if rec.get("_merged_from"):
        base["merged_from"] = rec["_merged_from"]

    body = rec["text"].strip()
    if len(body) <= SPLIT_MIN_CHARS:
        text = f"{rec['breadcrumb']}\n\n{body}"
        return [{**base, "chunk_id": rec["section_number"],
                 "sub_chunk_index": None, "n_sub_chunks": 1,
                 "text": text, "char_count": len(text)}]

    pieces = pack(to_segments(body))
    n = len(pieces)
    if n == 1:
        text = f"{rec['breadcrumb']}\n\n{pieces[0]}"
        return [{**base, "chunk_id": rec["section_number"],
                 "sub_chunk_index": None, "n_sub_chunks": 1,
                 "text": text, "char_count": len(text)}]

    records = []
    for i, piece in enumerate(pieces, 1):
        header = f"{rec['breadcrumb']} [{i}/{n}]"
        overlap = ""
        if i > 1:
            ov = last_sentence(pieces[i - 2])
            if ov:
                overlap = f"…{ov}\n\n"
        text = f"{header}\n\n{overlap}{piece}"
        records.append({**base, "chunk_id": f"{rec['section_number']}/{i}",
                        "sub_chunk_index": i, "n_sub_chunks": n,
                        "text": text, "char_count": len(text)})
    return records


# ==========================================================================
def pctl(vals, p):
    s = sorted(vals)
    k = (len(s) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main() -> int:
    sections, by_num = load_records()
    sections, merged_log = apply_merges(sections, by_num)
    for pnum, kids in merged_log.items():
        r = by_num.get(pnum.replace(" (created)", ""))
        if r is None:
            r = next((x for x in sections if x["section_number"] == pnum.replace(" (created)", "")), None)
        if r is not None:
            r["_merged_from"] = kids

    retrievable = [r for r in sections if not r["excluded_from_retrieval"]]
    retrievable.sort(key=lambda r: [int(p) for p in re.findall(r"\d+", r["section_number"])])

    chunks: list[dict] = []
    for r in retrievable:
        chunks.extend(chunk_records(r))

    CHUNKS_JSON.write_text(json.dumps({
        "source": "data/extracted/sections.json (+ recovered_sections.json)",
        "protocol": "MK-6482-005 / NCT04195750",
        "params": {"split_min_chars": SPLIT_MIN_CHARS, "subchunk_target": SUBCHUNK_TARGET,
                   "subchunk_max": SUBCHUNK_MAX},
        "counts": {
            "retrievable_sections": len(retrievable),
            "chunks": len(chunks),
            "split_sections": len({c["section_number"] for c in chunks if c["n_sub_chunks"] > 1}),
            "sub_chunks": sum(1 for c in chunks if c["sub_chunk_index"]),
            "partial_redaction_chunks": sum(1 for c in chunks if c["is_partial_redaction"]),
            "recovered_chunks": sum(1 for c in chunks if c["source"] == "pdfplumber"),
        },
        "chunks": chunks,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---- report ----
    lens = [c["char_count"] for c in chunks]
    print("=" * 70)
    print("CHUNK BUILD REPORT")
    print("=" * 70)
    print(f"retrievable sections in:        {len(retrievable)}")
    print(f"chunks out:                     {len(chunks)}")
    print(f"  split sections:               {len({c['section_number'] for c in chunks if c['n_sub_chunks']>1})}")
    print(f"  sub-chunks:                   {sum(1 for c in chunks if c['sub_chunk_index'])}")
    print(f"  single-chunk sections:        {sum(1 for c in chunks if c['n_sub_chunks']==1)}")
    print(f"  partial-redaction chunks:     {sum(1 for c in chunks if c['is_partial_redaction'])}")
    print(f"  pdfplumber-recovered chunks:  {sum(1 for c in chunks if c['source']=='pdfplumber')}")
    print(f"\nchunk char_count:  min {min(lens)}  p25 {pctl(lens,.25):.0f}  "
          f"median {statistics.median(lens):.0f}  p75 {pctl(lens,.75):.0f}  max {max(lens)}")
    over = [c for c in chunks if c["char_count"] > 2000]
    print(f"\nchunks over 2000 chars ({len(over)}):")
    for c in sorted(over, key=lambda c: -c["char_count"]):
        print(f"   {c['char_count']:>6}  {c['chunk_id']:<12} {c['section_title'][:44]}")
    tiny = [c for c in chunks if c["char_count"] < 250]
    print(f"\nchunks under 250 chars ({len(tiny)}):")
    for c in sorted(tiny, key=lambda c: c["char_count"]):
        print(f"   {c['char_count']:>6}  {c['chunk_id']:<12} {c['section_title'][:44]}")
    print("\nmerges applied:")
    for pnum, kids in merged_log.items():
        print(f"   {', '.join(kids)}  ->  {pnum}")
    print(f"\nsplit sections and their piece counts:")
    for sn in sorted({c["section_number"] for c in chunks if c["n_sub_chunks"] > 1},
                     key=lambda s: [int(p) for p in re.findall(r'\d+', s)]):
        cs = [c for c in chunks if c["section_number"] == sn]
        print(f"   {sn:<10} {cs[0]['n_sub_chunks']} parts  ({cs[0]['section_title'][:40]})  "
              f"[{', '.join(str(c['char_count']) for c in cs)}]")
    print(f"\nWrote {CHUNKS_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

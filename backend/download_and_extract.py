"""
Step 1 of the pipeline: fetch the source protocol PDF and extract its full text.

- Downloads the MK-6482-005 / NCT04195750 protocol PDF into data/raw/ (skips if
  already present).
- Extracts text page-by-page with PyMuPDF (fitz), preserving reading order.
- Writes the full text to data/extracted/protocol_text.txt, with a form-feed
  (\\f) between pages so later steps can recover page boundaries.
- Prints a summary (page count, char count, samples from start / middle / end)
  plus a quick running-header/footer probe, so we can eyeball extraction quality
  before designing the chunking strategy.

Run from the backend/ directory:  python download_and_extract.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf  # PyMuPDF (the old top-level name `fitz` is deprecated)
import requests

PDF_URL = "https://cdn.clinicaltrials.gov/large-docs/50/NCT04195750/Prot_000.pdf"

# Paths are resolved relative to the repo root (this file lives in backend/).
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = REPO_ROOT / "data" / "raw" / "Prot_000.pdf"
EXTRACTED_PATH = REPO_ROOT / "data" / "extracted" / "protocol_text.txt"

PAGE_SEP = "\f"  # form feed: conventional page-break marker, easy to split on


def download_pdf(url: str, dest: Path) -> None:
    if dest.exists():
        size_mb = dest.stat().st_size / 1_000_000
        print(f"PDF already present: {dest}  ({size_mb:.1f} MB) - skipping download")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        written = 0
        with open(dest, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=1 << 16):
                fh.write(chunk)
                written += len(chunk)
                if total:
                    pct = 100 * written / total
                    print(f"\r  {written/1_000_000:5.1f} / {total/1_000_000:.1f} MB "
                          f"({pct:4.0f}%)", end="")
        print()
    print(f"Saved to {dest}  ({dest.stat().st_size/1_000_000:.1f} MB)")


def extract_text(pdf_path: Path) -> list[str]:
    """Return a list of per-page text strings, in document order."""
    doc = pymupdf.open(pdf_path)
    pages = [page.get_text("text") for page in doc]
    doc.close()
    return pages


def write_extracted(pages: list[str], dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(PAGE_SEP.join(pages), encoding="utf-8")
    print(f"Wrote extracted text to {dest}")


def _sample(text: str, label: str, n: int = 900) -> None:
    print(f"\n{'-' * 70}\n{label} (first {n} chars)\n{'-' * 70}")
    print(text[:n].rstrip())


def print_summary(pages: list[str]) -> None:
    full = PAGE_SEP.join(pages)
    n_pages = len(pages)
    n_chars = len(full)
    empty_pages = [i + 1 for i, p in enumerate(pages) if not p.strip()]

    print(f"\n{'=' * 70}\nEXTRACTION SUMMARY\n{'=' * 70}")
    print(f"Pages:            {n_pages}")
    print(f"Characters:       {n_chars:,}")
    print(f"Avg chars/page:   {n_chars // n_pages:,}")
    print(f"Empty/blank pages: {len(empty_pages)}"
          + (f"  -> {empty_pages}" if empty_pages else ""))

    mid = n_pages // 2
    _sample(pages[0], "START  - page 1")
    _sample(pages[mid], f"MIDDLE - page {mid + 1}")
    _sample(pages[-1], f"END    - page {n_pages}")

    # Running-header / footer probe: first and last non-blank line of a spread
    # of pages. If the same text recurs, it's a running header/footer that will
    # need stripping before chunking.
    print(f"\n{'-' * 70}\nRUNNING HEADER / FOOTER PROBE "
          f"(first & last line of sampled pages)\n{'-' * 70}")
    sample_idxs = sorted({0, 1, 2, n_pages // 4, mid, 3 * n_pages // 4,
                          n_pages - 2, n_pages - 1})
    for idx in sample_idxs:
        lines = [ln.strip() for ln in pages[idx].splitlines() if ln.strip()]
        if not lines:
            print(f"  p{idx + 1:>3}: <blank>")
            continue
        print(f"  p{idx + 1:>3}  FIRST: {lines[0][:80]!r}")
        print(f"        LAST : {lines[-1][:80]!r}")


def main() -> int:
    download_pdf(PDF_URL, RAW_PATH)
    print("\nExtracting text with PyMuPDF ...")
    pages = extract_text(RAW_PATH)
    write_extracted(pages, EXTRACTED_PATH)
    print_summary(pages)
    return 0


if __name__ == "__main__":
    sys.exit(main())

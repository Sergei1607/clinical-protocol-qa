# Clinical Protocol Q&A

A retrieval-augmented chatbot that answers natural-language questions about a
real, publicly posted clinical trial protocol — **strictly from the protocol
text it retrieves**, never from general knowledge. Every answer shows the
sections it drew on and the actual retrieved excerpt behind each citation. When
the relevant text is redacted, or simply isn't in what was retrieved, the bot
says so instead of filling the gap with something plausible.

**Live app:** https://clinical-protocol-qa.vercel.app
**API:** https://clinical-protocol-qa.onrender.com
**Repo:** https://github.com/Sergei1607/clinical-protocol-qa

(The API is on Render's free tier — the first request after ~15 minutes idle
takes 30–60 seconds to wake up, because it re-downloads the embedding model on
cold start. Known free-tier tradeoff, not a bug — see *Known limitations*.)

**Portfolio project 3 of 3** — a clinical-AI portfolio themed around tools for
clinical study teams. Project 1 drafted safety narratives from structured data;
Project 2 was a SQL-tool agent over a trial database; this one is retrieval-
augmented Q&A over an unstructured, partially redacted protocol PDF.

## What it does

Ask it something like *"how should belzutifan dosing be modified if a
participant develops hypoxia?"* and it embeds the question, pulls the 8
most-similar protocol chunks out of a vector store, and asks Claude to answer
**using only those chunks** — then shows you which sections it used, with the
retrieved text expandable underneath each one as proof of grounding.

The document is **Protocol MK-6482-005 / NCT04195750** — Merck's Phase 3 study
of belzutifan (MK-6482) versus everolimus in advanced renal cell carcinoma
(results in *NEJM* 2024). The public PDF on clinicaltrials.gov is 166 pages and,
like most sponsor-posted protocols, has whole passages blacked out as
commercially confidential.

The point of the project is the grounding discipline:

- **No fallback to general knowledge.** The model is told to answer only from
  the retrieved chunks and not to reason about how "a trial like this usually"
  does something.
- **Redaction is surfaced, not skipped.** Where a retrieved chunk contains a
  `[REDACTED: …]` marker, the answer states that this specific information is
  withheld in the public protocol — it never guesses what was removed.
- **"Not retrieved" is a valid answer.** If nothing retrieved actually addresses
  the question, the bot says that plainly (and still lists any partial,
  related detail it did find, cited).

## Tech stack

| Layer | Choice |
|---|---|
| **Frontend** | React + Vite + TypeScript + Tailwind CSS, deployed on Vercel |
| **Backend** | FastAPI (Python 3.12), deployed on Render |
| **Vector store** | Supabase (free-tier Postgres) + `pgvector`, HNSW cosine index |
| **Embeddings** | `BAAI/bge-small-en-v1.5` (384-dim), run locally on **ONNX Runtime** — no API key, no cost, no GPU |
| **LLM** | Claude API (`claude-sonnet-5`), one grounded call per question — no agent loop |
| **PDF pipeline** | PyMuPDF for full-text extraction; pdfplumber for scoped table recovery |

Same free-tier-only constraint as the rest of the portfolio: nothing here needs
a credit card. The only paid usage is Claude API tokens (~$0.01–0.015 per
question).

## Pipeline and key design decisions

This is the part worth reading closely. The pipeline is six scripts in
`backend/`, run in order; each writes a JSON artifact the next one consumes.

### 1. Extraction — and what a sponsor protocol PDF actually throws at you

`download_and_extract.py` pulls the ~304k-character text out of the 166-page PDF
with PyMuPDF (it's a digital PDF, no OCR needed). `parse_sections.py` then has to
clean it. The mess, and how each part was handled:

| Problem | Handling |
|---|---|
| **5-line running header** (`PRODUCT: MK-6482` / page no. / `PROTOCOL/AMENDMENT NO.: 005-09` / …) injected mid-sentence at every page break | Detected by its fixed first line and length, stripped, text re-joined across the break |
| **`08RD3B` running footer** on all 165 body pages | Stripped |
| **Header page-number line** creating false section headings (a bare integer followed by known header text) | Filtered before heading detection |
| **Line-break hyphenation** kept literally (`follow-`⏎`up`) | De-hyphenated on re-join, so `"follow-up"` queries match |
| **Mixed bullet glyphs** — `•` (186), a private-use char (71), `◦` (15), `●` (6) | Normalized to one marker |
| **CCI redaction token** — Merck's blackout marker, 111 occurrences, often stacked 5–14 deep; 10 pages are 100% redacted | Collapsed each stack to a single `[REDACTED: commercially confidential information]` marker, attributed to that page's section |
| **Flattened tables** — multi-column tables collapse to one-cell-per-line noise | Detected and excluded (14 sections), then the two most important recovered separately — see below |

### 2. Structure-aware chunking, cross-validated against the TOC

Rather than blind fixed-size slicing, chunks follow the protocol's own section
structure:

- The **Table of Contents** (printed pages 6–12) is parsed into an ordered
  `section number → (title, page)` map — 199 entries, 17 of which are
  dot-leader-only, marking sections that were redacted away entirely.
- The body is walked for headings (the protocol renders them reliably as
  *number alone on one line, title on the next*), and **every detected heading
  is cross-checked against the TOC title** so a stray `"2.1"` in prose doesn't
  register as a section boundary. Discrepancies are collected and reported, not
  silently patched.
- Result: **171 section records** (150 leaf sections + 21 section preambles);
  155 retrievable, 2 fully redacted, 14 excluded as flattened tables, 19 with
  partial redaction. This file (`sections.json`) is the source of truth and is
  never mutated by later steps.

`build_chunks.py` then turns those into the retrieval set:

- **Long sections are split** (over 1,800 chars) into ~1,200-char sub-chunks,
  preferring numbered-list-item boundaries, then sub-bullets, then paragraphs,
  then sentences — **never mid-list-item, and never splitting a Markdown
  table.** An eligibility criteria list stays whole. Each sub-chunk repeats the
  full section breadcrumb + an `[i/n]` index and carries ~1 sentence of overlap
  from the previous one.
- **Tiny leaf sections** (11 of them, under ~150 chars) are merged into their
  parent chunk.
- **Section 11 REFERENCES is dropped** — it's a bibliography, not something
  anyone runs Q&A against.
- Final set: **219 chunks over 148 sections** (28 sections became 99 sub-chunks;
  30 chunks carry a redaction marker). Chunk length p25 / median / p75 =
  626 / 1,042 / 1,448 chars.

### 3. Redaction handling

The `[REDACTED: …]` markers are **preserved through the whole pipeline** —
extraction, chunking, embedding, retrieval, and into the answer. They're never
stripped (which would make a redacted section look like a normal one) and never
guessed at. The frontend pulls the marker out of the excerpt into an amber
badge, and the answer explicitly names the redaction. A partially-redacted
section is still retrievable and still useful for the parts that *aren't*
redacted.

### 4. The pdfplumber table-recovery call — Synopsis and Objectives in, 12 others out

PyMuPDF's plain-text pass flattens every multi-column table into an unreadable
vertical stream. Fixing that properly is per-table hand-work: `recover_tables.py`
re-reads a specific page range with pdfplumber, pulls the real grid with
`find_tables()`, renders it as a Markdown table, and interleaves it with the
non-table prose on the same pages by vertical position. It is **hard-coded to
two page ranges**, not a general parser.

I spent that effort on the two tables that carry the most Q&A value:

- **§1.1 Synopsis** (printed pp. 15–18) — the study-at-a-glance: design, arms,
  dosing, duration, sample size.
- **§3 Hypotheses, Objectives, and Endpoints** (pp. 42–43) — the primary /
  secondary / tertiary objective-endpoint matrix.

Both recovered clean (5 chunks) and went back into the corpus.

The other **12 flattened tables were left excluded** deliberately — the
effort-to-value ratio didn't hold up:

- **§1.3 Schedule of Activities** (~15 pages) is the worst offender and would be
  the most work; it's also the one case where the bot's "that table isn't in
  the retrieved excerpts" honesty behavior is genuinely useful to demonstrate.
- §6.1 / §6.6.1 (dosing-modification tables), §8.4.1, §9.6.1.5, §10.2 (the
  Appendix 2 lab-test list), §10.7.1–10.7.5 (country-specific requirement
  tables), §10.9 — each is niche, and the prose around them usually carries the
  gist. The bot discloses when it's missing one rather than pretending
  otherwise.

### 5. Embeddings, and the ONNX pivot

**Model choice: `bge-small-en-v1.5` over `all-MiniLM-L6-v2`.** Same size class
(384-dim, ~33M params, CPU-friendly) but bge-small ranks meaningfully higher on
MTEB retrieval and uses a query-instruction convention (`"Represent this
sentence for searching relevant passages: "` prepended to queries only, never to
passages) that's well-suited to asymmetric question→passage search. Pooling is
CLS-token + L2-normalize.

**The pivot: torch OOM'd on Render's free tier.** The first Render deploy failed
— `torch` + `sentence-transformers` loading the model exceeded the 512 MB
memory limit (importing `sentence_transformers` pulls in torch unconditionally,
~200 MB resident before the model even loads — even with its `backend="onnx"`
option).

So `backend/embed_onnx.py` runs the *same model* on `onnxruntime` +
`tokenizers` directly: tokenize → ONNX forward pass → CLS pool → L2 normalize,
by hand, with no torch anywhere in the deployed import graph. The ONNX graph and
tokenizer come from the BAAI repo itself (it ships `onnx/model.onnx`) and are
cached like any HF download.

Verified before shipping it:

| Check | Result |
|---|---|
| Output vs. the torch path, 6 sample texts (incl. a 512-token truncation case) | **cosine 1.000000**, max absolute element difference **0.000000**, L2 difference ~1e-6 (float32 rounding) |
| Full 18-question eval, all 219 chunks re-embedded through ONNX | **byte-identical to the pre-pivot baseline** — same judge verdict, same retrieval rank, and the same top-8 chunk-id list for every question |
| Local process memory after loading the model + one embed | ~270 MB RSS (was OOM at 512) |
| Single-query embed latency | ~8–10 ms |

Dropped from `requirements.txt`: torch (~200 MB), sentence-transformers,
transformers, scipy, scikit-learn. Added: onnxruntime (~14 MB), tokenizers,
huggingface-hub. Numerically it's the same retriever; it just fits now.

### 6. Retrieval, generation, and the formal eval

**Retrieval:** embed the question, `pgvector` cosine top-k (k = 8) against the
219-row `protocol_chunks` table, via a `SELECT`-only database role. Two roles,
same pattern as Project 2 — an owner connection used only by the local loader
(never present in the deployed environment) and `app_readonly` for the running
API.

**Generation:** one `client.messages.create` call (`claude-sonnet-5`, no
tool-use loop). The system prompt is the actual product: answer only from the
chunks; on a `[REDACTED]` marker, say the info is withheld and don't infer it;
if nothing addresses the question, say it's not in the excerpts and don't fall
back on what a trial "should" do; end every answer with a machine-parseable
`SOURCES:` block, one line per section actually used. The `/ask` response
carries the answer, the parsed citations, and — per cited section — the *actual
retrieved excerpt text*, which is what the frontend shows as proof of grounding.

**Eval harness** (`eval/run_eval.py`, `eval/eval_set.json`): 18 hand-built
questions, scored on two axes:

- **Retrieval recall** (programmatic, no LLM): for the 14 questions with an
  expected section, did it land in the top-8, and at what rank.
- **Answer quality** (LLM-as-judge, Claude Sonnet): graded against a per-
  question rubric of `expected_behavior` (`answer` / `redacted` /
  `not_in_excerpts` / `should_refuse_outside_knowledge`) and expected key facts.

The 18 cover: normal answerable questions (13), a redacted section (1),
questions whose answer is in a deliberately-excluded part of the document (2), a
paraphrase-sensitivity probe (q10), and adversarial questions that need
*outside* knowledge, where the correct behavior is refusing (2 — FDA approval
status, and published trial results).

| Run | Judge pass rate | Retrieval recall |
|---|---|---|
| **v1** (baseline) | 17 / 18 (94.4%) — 1 borderline, 0 fail | 14 / 14 (100%) |
| **v2** (after one generic prompt tweak) | **18 / 18 (100%)** — 0 regressions | 14 / 14 (100%) |
| **onnx** (after the embedding pivot, re-embedded) | 18 / 18 (100%) | 14 / 14 (100%) |

The v1 borderline (q12, on how the overall-survival treatment difference is
analyzed) dropped a Kaplan-Meier detail that was in the retrieved text. The fix
was **one generic sentence** added to the system prompt — *"when a retrieved
excerpt enumerates multiple relevant items, include all of them"* — phrased to
not mention Kaplan-Meier or q12 specifically. It fixed q12, lifted key-fact
coverage on two other questions, caused no regressions, and cost ~22% more
output tokens (concentrated on one question that now recites a full risk-factor
definition). Kept, with the tradeoff noted.

## Notable finding — the honesty behavior actually holds up

The thesis of this project is that a RAG bot can be made to reliably *decline*
rather than fabricate. Three cases from the eval, with what the bot actually
said:

**Redacted content** — *"What are the tertiary and exploratory objectives and
endpoints of the study?"* (§3 has this row blacked out):

> The tertiary/exploratory objectives and endpoints section is present in the
> retrieved excerpts, but the content itself is redacted: "[REDACTED:
> commercially confidential information]" (§3, Table of Objectives/Endpoints).
> No other chunk provides this detail.

**Deliberately excluded content** — *"What is the full schedule of study
assessments by visit week during the treatment period?"* (the Schedule of
Activities table is not in the corpus):

> Based on the retrieved excerpts, I cannot provide the "full schedule"
> (visit-by-visit table). The excerpts explicitly note that visit requirements
> are outlined in the Schedule of Activities (SoA, Section 1.3), which is not
> included in this retrieval set. I can only report the specific scheduling
> details that appear in the provided chunks: …

— and it then lists the genuine fragments it found (Week 9 first imaging, Q8W
thereafter, PRO assessment weeks, the 30-day follow-up visit), each cited,
before restating that the consolidated table isn't there.

**Outside knowledge** — *"What is belzutifan's current FDA approval status for
renal cell carcinoma?"*:

> The retrieved protocol excerpts do not contain information about belzutifan's
> FDA approval status for renal cell carcinoma. The chunks discuss the study
> rationale, preclinical/clinical data, and statistical plan, but do not
> address regulatory approval status.
>
> SOURCES:
> - none

Belzutifan *is* FDA-approved for RCC (Dec 2023), and a general-purpose model
would happily say so — but that fact is not in this protocol, so the bot
doesn't.

## Deliberately scoped out

- **The Schedule of Activities and ~12 other flattened multi-column tables.**
  Recovery is per-table hand-tuning (see pipeline §4). Did the two
  highest-value tables; left the rest as gaps the bot discloses rather than
  papers over.
- **Section 11 (References).** A bibliography. Nobody asks a protocol Q&A bot to
  cite reference 47.
- **Document History / Amendment Summary of Changes** (printed pages 3–6).
  These describe what changed *between amendment versions* and name dozens of
  old `"Section X.Y"` strings in prose — meta-content that would pollute
  citations and confuse "what does the protocol say now."
- **Multi-turn conversation memory.** Every `/ask` is independent. The frontend
  keeps the transcript for display only; there's no server-side session and no
  history sent back. Same deliberate call as Projects 1 & 2 — conversational
  RAG is a bigger project.
- **Auth / rate limiting on `/ask`.** Acceptable for an unlisted portfolio demo
  on a free tier; not for anything real.

## Known limitations

Stated plainly, same as Projects 1 & 2:

- **Render cold start, now with a model download.** Free tier spins down after
  ~15 minutes idle. Because the free tier has **no persistent disk**, the
  ~133 MB ONNX model is re-downloaded from Hugging Face on every cold start, so
  the first request takes 30–60 seconds (up from ~20–30 in Projects 1 & 2).
- **Supabase pause.** The free-tier database pauses after ~1 week of no
  activity and needs a visit to the Supabase dashboard to resume. If the live
  app returns database errors, this is why.
- **Retrieval is phrasing-sensitive.** Eval q10 — *"if someone had a surgical
  procedure recently, does the protocol bar them from joining?"* — retrieves
  §5.2 Exclusion Criteria but the *wrong sub-chunk* (5.2/6, not the 5.2/3 that
  holds the major-surgery washout criterion), so the bot says it can't find it.
  The specifically-worded versions (*"major surgery three weeks ago"*, q02/q09)
  *do* find it. The bot fails safe — it defers instead of guessing — but it's a
  real recall gap on vague paraphrases.
- **HF_TOKEN not set.** The ONNX download logs an *"unauthenticated requests to
  the HF Hub"* warning. Anonymous rate limits are fine for one public-model
  download per cold start, and wiring in a token means managing another secret
  for a marginal speed gain — an acceptable skip for this scale, not for a
  service that restarts often.
- **No auth on the endpoint.** As above — unlisted demo only.

## What I'd improve next

- **Close the phrasing-sensitivity gap** — a cross-encoder rerank over the
  top-k, or moving to `bge-base` / a larger embedding model, so a vague
  paraphrase of an exclusion criterion still surfaces the right sub-chunk.
- **Generalize the table recovery to the Schedule of Activities**, so *"what
  assessments happen at Week 9?"* becomes directly answerable instead of a
  disclosed gap.
- **Cache the ONNX model on a persistent volume** (or bake it into the deploy
  image) to kill the cold-start re-download.
- **Auth + rate limiting** before this is anything more than a portfolio demo.

## Running locally

### Backend

```
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# create .env from .env.example and fill in:
#   SUPABASE_READONLY_URL   (app_readonly role — what the API uses)
#   ANTHROPIC_API_KEY
#   SUPABASE_OWNER_URL      (owner role — only for the one-time data load)

# one-time: build the corpus and load it (needs the owner URL)
python download_and_extract.py
python parse_sections.py
python recover_tables.py
python build_chunks.py
python setup_supabase.py
python load_embeddings.py

# run the API
python main.py            # honours $PORT; defaults to 8000
```

`data/` artifacts are gitignored and re-buildable; the Supabase table is
already populated (219 rows), so a fresh checkout only needs the read-only URL
and the API key to run the app.

### Frontend

```
cd frontend
npm install
# create .env from .env.example:  VITE_API_URL=http://localhost:8000
npm run dev
```

Then open http://localhost:5173.

## License / data note

Protocol MK-6482-005 is published by its sponsor on clinicaltrials.gov and is
used here only as public reference material for a non-commercial portfolio demo.
All protocol content belongs to its sponsor.

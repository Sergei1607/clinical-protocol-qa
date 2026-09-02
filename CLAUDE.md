# Project: Clinical Protocol Q&A (RAG chatbot) — Portfolio Project 3 of 3

## What this is
A retrieval-augmented Q&A web app over a real clinical trial protocol PDF. User
asks a natural-language question; the app retrieves the most relevant protocol
chunks from a vector store, sends them to Claude as grounding context, and
returns an answer **strictly grounded in the retrieved text**, with a citation
back to the protocol section used. Third and final CV portfolio project, themed
around AI tools for clinical study teams.

Full plan for all 3 projects lives in the roadmap doc in the parent Claude
Project (not in this repo). This file carries only what's relevant to *this* repo.

## Hard constraint
**Zero budget beyond Claude API token usage.** Never introduce a paid service,
paid tier, or anything requiring a credit card. Free tier or open-source only.
Flag it explicitly if something would cost money — don't assume it's fine.

## Stack
- **Backend:** Python + FastAPI — deploy target: Render (free tier; ~15 min
  spin-down / cold start on free instances, same as Projects 1 & 2).
- **Frontend:** React + Vite + Tailwind CSS — deploy target: Vercel (free Hobby
  tier). Reuses the chat UI pattern from Project 2.
- **Embeddings:** `sentence-transformers` running locally on CPU — no API key,
  no cost. (Model choice TBD; likely `all-MiniLM-L6-v2` or `BAAI/bge-small-en`.)
- **Vector store:** Supabase (hosted Postgres + `pgvector` extension), free
  tier. Caveat: free Supabase projects **pause after ~1 week of inactivity** and
  need a manual resume from the dashboard — expect this when returning to the
  project after a break, and mention it in the README/demo notes.
- **LLM:** Claude API, single-call answer generation with retrieved context
  (not an agent loop).
- **PDF extraction:** PyMuPDF (`pymupdf` / `fitz`). Chosen over pdfplumber for
  speed on a 162-page doc and for its layout/coordinate data, which helps detect
  section boundaries for chunking. pdfplumber can be added later *only* if
  specific tables need precise cell-level extraction.
- **Version control:** GitHub, one commit per feature, clear messages — not one
  giant commit at the end.

## Source document
Protocol MK-6482-005 / NCT04195750 — Phase 3, belzutifan (MK-6482) vs everolimus
in advanced renal cell carcinoma. Public PDF (~162 pages) from clinicaltrials.gov:
`https://cdn.clinicaltrials.gov/large-docs/50/NCT04195750/Prot_000.pdf`
Downloaded to `data/raw/` by the pipeline (gitignored — re-downloadable).

## My background (so you calibrate correctly)
- **Solid:** Python, FastAPI, HTML/CSS/JS, Git/GitHub, Vercel/Render deploys, the
  Claude Code approve/review workflow, prompt design for single-call Claude API
  features. Day job: Business Analyst in Clinical Data & Analytics
  (Spotfire/IronPython, clinical trial data) — so I know the *domain* well.
- **New — teach from fundamentals as they come up:**
  - React / Vite / Tailwind CSS (this is my 3rd project touching them but still
    shaky; don't assume React knowledge).
  - SQL / Postgres — basic queries only; assume little.
  - Embeddings / vector search / RAG — the whole concept is new. Explain
    chunking, embedding models, cosine similarity, top-k retrieval, and why
    grounding matters, when each comes up.

## Environment
- **Windows 11, working natively** — confirmed across Projects 1 & 2 that
  Node / Python / git all run fine natively; no WSL2 needed. Vercel and Render
  build in their own Linux containers regardless.
- Python: **`backend/.venv` runs Python 3.12.10** (`py -3.12`, installed via
  `winget install Python.Python.3.12 --scope user`). Switched from 3.14 up front
  because `torch` / `sentence-transformers` (needed for the embeddings step) do
  not ship 3.14 wheels yet and would fail to build from source. 3.14 is still the
  machine default (`py -3.14`); use `py -3.12` for anything in this repo.
- Shell: PowerShell primary.

## How to work with me
- **One step at a time for setup/install** — run it, show me the output, confirm
  it worked before moving on.
- Point out what's fragile or what an interviewer would poke at.
- Ask before generating anything nontrivial rather than assuming — I'd rather
  clarify up front than redo work.
- One commit per feature, not one mega-commit at the end.
- Reasonably efficient pace; skip "explain it back to me" comprehension checks,
  but do explain new concepts (see "New" list above) as they arise.

## Repo structure
```
clinical-protocol-qa/
├── backend/              # Python: FastAPI app + data pipeline scripts
│   ├── .venv/            # gitignored
│   └── requirements.txt
├── data/
│   ├── raw/              # source protocol PDF (gitignored, re-downloadable)
│   └── extracted/        # extracted plain text for inspection (gitignored)
├── frontend/             # React + Vite + Tailwind — NOT created yet
├── CLAUDE.md
└── README.md
```
Frontend and the FastAPI app itself come later — too early now.

## Build order (this project)
1. **Scaffold** — repo, .gitignore, README stub, this file, folder structure,
   backend venv, PDF download + full-text extraction script. Eyeball extraction
   quality. ✅ done
2. **Section parsing** — clean text, detect section boundaries, parse TOC to a
   section→page map, flag CCI redactions, exclude flattened tables, emit
   `data/extracted/sections.json`. ✅ done (`backend/parse_sections.py`)
2b. **Chunking** — recover Synopsis + Section 3 tables (pdfplumber), split long
   sections, merge tiny ones, emit `data/extracted/chunks.json`. ✅ done
   (`backend/recover_tables.py`, `backend/build_chunks.py`)
3. **Embed + store** — BAAI/bge-small-en-v1.5 (384-dim), embed `chunks.json`,
   load into Supabase `protocol_chunks` (pgvector), validate retrieval by hand.
   ✅ done (`setup_supabase.py`, `load_embeddings.py`, `test_retrieval.py`)
4. **Retrieval + answer endpoint** — FastAPI `POST /ask`: embed question → top-k
   (k=8) retrieve → single grounded Claude call → answer + parsed citations.
   ✅ done (`backend/rag.py`, `backend/main.py`, `backend/test_ask.py`)
4b. **Eval harness** — `eval/eval_set.json` (18 Qs) + `eval/run_eval.py`: per-Q
   retrieval recall + LLM-judge (Sonnet) → `eval/results.{json,md}`. ✅ done
   (baseline: 17/18 pass, 1 borderline, 100% section-level retrieval recall)
5. **Frontend** — chat UI (reuse Project 2 pattern): question box, answer view,
   visible citation, link/expand to the cited chunk. ← *current step*
6. **Deploy** — Render (backend) + Vercel (frontend); verify the *live* app
   works, not just that the deploy succeeded. Note Supabase pause behavior.
7. **README** — what it does, stack, live link, RAG design notes, what I'd
   improve next.

## Definition of done
Deployed, working protocol Q&A app with a real React UI, answers grounded in
retrieved chunks with visible section citations, chunking done on real section
boundaries, README with live link.

## Current status
Repo scaffolded; PDF extracted (166 pages); backend venv on Python 3.12.

Pipeline (all in `backend/`, run in order):
- `download_and_extract.py` → `data/extracted/protocol_text.txt`
- `parse_sections.py` → `data/extracted/sections.json` (source-of-truth section
  records; 171 records, NOT modified by later steps)
- `recover_tables.py` → `data/extracted/recovered_sections.json` (pdfplumber
  re-extraction of 1.1 Synopsis + 3 Objectives/Endpoints — both recovered clean)
- `build_chunks.py` → `data/extracted/chunks.json` — **the retrieval chunk set**:
  219 chunks from 148 retrievable sections (28 sections split into 99 sub-chunks;
  11 tiny sections merged into parents; §11 REFERENCES excluded as
  `non-qa-content`). char_count p25/median/p75 = 631 / 1042 / 1448.
- `setup_supabase.py` → `protocol_chunks` table (pgvector, HNSW cosine index) in
  the Project 2 Supabase project; `app_readonly` granted SELECT on it.
- `load_embeddings.py` → embeds all 219 chunks with **BAAI/bge-small-en-v1.5**
  (384-dim, CPU, ~8s to embed + ~7s to upsert) and idempotently upserts rows.
- `test_retrieval.py` → 6 hand questions, cosine query via `app_readonly`.

bge convention: query text is prefixed with
`"Represent this sentence for searching relevant passages: "`; **chunk/passage
text is not**. Torch is CPU-only (`torch==2.14.0+cpu`, `--extra-index-url` in
requirements.txt) — no GPU locally or on Render.

- `rag.py` -> `answer_question(q, k=8)`: embed query -> pgvector top-k via
  `app_readonly` -> **one** `client.messages.create` (no tool loop) -> parse the
  `SOURCES:` block. `main.py` -> FastAPI `POST /ask` + `GET /health`, model warmed
  at startup, open CORS, **no auth** (portfolio-demo call, note for README).
  `test_ask.py` -> 10 questions (6 original + 4 rephrasings).
- Answer model: **`claude-sonnet-5`** (env `ANSWER_MODEL` overrides). Sonnet not
  Opus because of the zero-budget constraint; grounded extraction is in range.
  ~$0.01-0.015/question. Citation format Claude must emit: `SOURCES:` then one
  `- §<num> | <title> | p.<start>-<end>` line per section actually used.

DB access: `backend/.env` (gitignored) holds `SUPABASE_OWNER_URL` (local only,
DDL + writes), `SUPABASE_READONLY_URL` (`app_readonly`, the API path), and
`ANTHROPIC_API_KEY`. See `backend/.env.example`.

- `eval/` — reusable harness. `eval_set.json`: 18 Qs (10 from test_ask + 8 new)
  each with expected_sections / expected_behavior / expected_keyfacts.
  `run_eval.py`: programmatic retrieval-recall + Sonnet LLM-judge →
  `results.{json,md}`. Baseline run: **17/18 judge pass, 1 borderline (q12 —
  answer omitted the Kaplan-Meier keyfact), 0 fail; retrieval recall 14/14
  (section granularity — q10's §5.2 hit was the wrong sub-chunk, bot correctly
  deferred)**. Judge switched Haiku→Sonnet (Haiku ignored the `also_acceptable`
  rule on q10). ~$0.22/run.

Decisions locked in: §11 excluded; 6.1/6.6.1/8.4.1/10.2/9.3 stay excluded (no
salvage); 1.1 + 3 recovered via pdfplumber and back in the corpus. Eval failures
NOT yet acted on — review together before changing chunking/retrieval/prompt.

**Next: React frontend.** Grounding/honesty is solid across the 18-Q eval
(redaction → "redacted"; excluded SoA/Appendix-2 → "not in the excerpts, here's
what is"; outside-knowledge → refuse; retrieval miss → "can't answer from these").
Known: retrieval is phrasing-sensitive — specific wording finds the exclusion
criterion, vague wording doesn't, but the bot says so. Candidate fixes for later:
bge-base, sibling-sub-chunk fetch, hybrid keyword search.

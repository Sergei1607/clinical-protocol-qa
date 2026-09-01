# clinical-protocol-qa

RAG chatbot that answers natural-language questions about a real clinical trial
protocol document, with each answer citing the source section it came from.

**Portfolio project 3 of 3** — a clinical-AI portfolio themed around tools for
clinical study teams. Project 1 drafted safety narratives from structured data;
Project 2 was an agentic workflow; this one is retrieval-augmented Q&A over an
unstructured protocol PDF.

## What it does

1. Ingests a real clinical trial protocol PDF.
2. Chunks it along real section boundaries (not blind fixed-size slicing).
3. Embeds chunks with a local `sentence-transformers` model (no API key, no cost).
4. Stores vectors in Supabase (Postgres + `pgvector`).
5. Answers questions grounded strictly in retrieved chunks, returning a citation
   to the protocol section each answer draws from.

## Source document

Protocol MK-6482-005 / NCT04195750 — "An Open-label, Randomized Phase 3 Study of
MK-6482 (Belzutifan) Versus Everolimus in Participants with Advanced Renal Cell
Carcinoma That Has Progressed After Prior PD-1/L1 and VEGF-Targeted Therapies"
(Merck; results in NEJM 2024). Public PDF via clinicaltrials.gov, ~162 pages.

## Stack

| Layer     | Choice                                              |
|-----------|----------------------------------------------------|
| Backend   | Python + FastAPI                                    |
| Frontend  | React + Vite + Tailwind (chat UI reused from Proj 2)|
| Embeddings| `sentence-transformers` (local, CPU)                |
| Vector DB | Supabase Postgres + `pgvector` (free tier)          |
| LLM       | Claude API                                          |
| Deploy    | Backend → Render, Frontend → Vercel (both free tier)|

## Status

Just started. Repo scaffolded; protocol PDF download + full-text extraction
pipeline in place. Chunking strategy not yet designed — that's next.

## Local setup

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
python download_and_extract.py
```

## License / data note

All protocol content belongs to its sponsor and is used here only as public
reference material for a non-commercial portfolio demo.

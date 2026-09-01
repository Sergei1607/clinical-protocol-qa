"""
FastAPI app for the clinical protocol Q&A bot.

One endpoint: POST /ask  {"question": "...", "k": 8}
-> embed question -> pgvector top-k -> single grounded Claude call -> answer + citations.

No auth / rate limiting: acceptable for an unlisted portfolio demo, same call made
in Projects 1 & 2 (note this in the README). No conversation history yet - single
question in, single answer out.

Run locally:  uvicorn main:app --reload   (from backend/)
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import rag


@asynccontextmanager
async def lifespan(app: FastAPI):
    rag.warm()          # load the embedding model once, at startup
    yield


app = FastAPI(title="Clinical Protocol Q&A", lifespan=lifespan)

# Frontend (Vercel) will call this cross-origin; wide-open CORS is fine for a
# public read-only demo. Tighten to the deployed frontend origin later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    k: int = Field(default=rag.DEFAULT_K, ge=1, le=20)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": rag.ANSWER_MODEL, "embed_model": rag.EMBED_MODEL}


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    return rag.answer_question(req.question, req.k)

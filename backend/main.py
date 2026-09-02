"""
FastAPI app for the clinical protocol Q&A bot.

One endpoint: POST /ask  {"question": "...", "k": 8}
-> embed question -> pgvector top-k -> single grounded Claude call -> answer + citations.

No auth / rate limiting: acceptable for an unlisted portfolio demo, same call made
in Projects 1 & 2 (note this in the README). No conversation history yet - single
question in, single answer out.

Run locally:  uvicorn main:app --reload   (from backend/)
Run in prod:  python main.py              (honours $PORT; Render sets it)
"""

from __future__ import annotations

import os
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

# The frontend (Vercel) calls this cross-origin. Default is wide-open, which is
# acceptable for a public read-only demo with no auth and no cookies. Once the
# Vercel URL exists, set ALLOWED_ORIGIN in the Render dashboard to lock it down -
# comma-separated for more than one - and restart. No code change needed.
#   ALLOWED_ORIGIN=https://clinical-protocol-qa.vercel.app
_allowed = [o.strip() for o in os.environ.get("ALLOWED_ORIGIN", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed or ["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    k: int = Field(default=rag.DEFAULT_K, ge=1, le=20)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": rag.ANSWER_MODEL,
        "embed_model": rag.EMBED_MODEL,
        "embed_backend": rag.EMBED_BACKEND,
    }


@app.post("/ask")
def ask(req: AskRequest) -> dict:
    return rag.answer_question(req.question, req.k)


if __name__ == "__main__":
    # Render (and most PaaS) assign the port at runtime via $PORT. Bind 0.0.0.0
    # so the container is reachable. No --reload in prod. Pass the app object
    # directly so the module isn't re-imported.
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))

# frontend — Clinical Protocol Q&A

React + Vite + Tailwind chat UI for the protocol Q&A bot. Client-side transcript
only (no server session); each question is an independent `POST /ask` to the
FastAPI backend. Deployed to Vercel with this folder as the root directory.

## Run locally

```bash
npm install
cp .env.example .env       # VITE_API_URL -> the backend
npm run dev                 # http://localhost:5173
```

The backend must be running (`cd ../backend && uvicorn main:app --reload`).

## The Sources block

Each answer carries a collapsible **Sources** block (collapsed by default). Each
source shows `§<section> <title> · p.<range>`; expanded, it shows the *actual
retrieved protocol excerpt* the answer drew from, in a bordered monospace quote
so it reads as source material, not more of the answer. A `[REDACTED: ...]`
marker inside an excerpt is pulled out into an amber badge, and the block header
shows a "contains redaction" tag.

## Config

`VITE_API_URL` (see `.env.example`) — the backend base URL. `http://localhost:8000`
for dev; repoint at the Render URL for the deployed build, no code change.

## `scripts/screenshot.mjs`

Dev helper — drives the running app with headless Chrome (`puppeteer-core`,
points at the local Chrome install) and saves a full-page screenshot. Needs the
dev server + backend up.

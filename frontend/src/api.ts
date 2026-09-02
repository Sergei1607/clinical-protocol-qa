// Talks to the FastAPI backend's POST /ask.
// Base URL comes from VITE_API_URL so it can be repointed at the deployed Render
// backend without a code change (see .env / .env.example).

const API_URL = (import.meta.env.VITE_API_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export const REDACTION_MARKER = '[REDACTED: commercially confidential information]'

export interface Source {
  section_number: string
  section_title: string
  page_start: number
  page_end: number
  excerpt_text: string | null
  is_partial_redaction: boolean
  contains_redaction_marker: boolean
  unmatched: boolean
}

export interface AskResponse {
  question: string
  answer_text: string
  sources: Source[]
  model: string
}

export async function ask(question: string, signal?: AbortSignal): Promise<AskResponse> {
  const res = await fetch(`${API_URL}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
    signal,
  })
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep the status-line detail */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<AskResponse>
}

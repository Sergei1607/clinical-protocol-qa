import { REDACTION_MARKER } from '../api'

// Renders the raw retrieved protocol text. Any [REDACTED: ...] marker is pulled
// out into an obvious inline badge so it can't be skimmed past as plain text.
export function Excerpt({ text }: { text: string }) {
  const parts = text.split(REDACTION_MARKER)
  return (
    <div className="whitespace-pre-wrap break-words font-mono text-[13px] leading-relaxed text-ink-soft">
      {parts.map((part, i) => (
        <span key={i}>
          {part}
          {i < parts.length - 1 && (
            <span className="mx-0.5 inline-block rounded bg-amber-100 px-1.5 py-0.5 font-sans text-[11px] font-semibold tracking-wide text-amber-800 uppercase ring-1 ring-amber-300">
              redacted — commercially confidential
            </span>
          )}
        </span>
      ))}
    </div>
  )
}

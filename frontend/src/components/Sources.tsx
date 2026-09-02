import { useState } from 'react'
import type { Source } from '../api'
import { Excerpt } from './Excerpt'

function pageLabel(s: Source) {
  return s.page_start === s.page_end ? `p.${s.page_start}` : `p.${s.page_start}-${s.page_end}`
}

export function Sources({ sources }: { sources: Source[] }) {
  const [open, setOpen] = useState(false)
  if (sources.length === 0) return null

  const anyRedacted = sources.some((s) => s.contains_redaction_marker)

  return (
    <div className="mt-3 rounded-lg border border-slate-200 bg-white/60">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-medium text-ink-soft hover:text-ink"
      >
        <svg
          className={`h-3.5 w-3.5 shrink-0 transition-transform ${open ? 'rotate-90' : ''}`}
          viewBox="0 0 12 12"
          fill="none"
          aria-hidden
        >
          <path d="M4 2.5 8 6l-4 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Sources ({sources.length})
        {anyRedacted && (
          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-amber-800 uppercase">
            contains redaction
          </span>
        )}
        <span className="ml-auto text-xs font-normal text-slate-400">
          {open ? 'hide excerpts' : 'show excerpts'}
        </span>
      </button>

      <ul className="divide-y divide-slate-100 border-t border-slate-200">
        {sources.map((s, i) => (
          <li key={i} className="px-3 py-2.5">
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm">
              <span className="font-semibold text-ink">§{s.section_number}</span>
              <span className="text-ink-soft">{s.section_title}</span>
              <span className="text-slate-400">· {pageLabel(s)}</span>
            </div>

            {open &&
              (s.excerpt_text ? (
                <blockquote className="mt-2 border-l-2 border-accent-soft bg-slate-50 py-2 pr-2 pl-3">
                  <Excerpt text={s.excerpt_text} />
                </blockquote>
              ) : (
                <p className="mt-1.5 text-xs text-slate-400 italic">
                  This section was cited but its text was not in the retrieved excerpts.
                </p>
              ))}
          </li>
        ))}
      </ul>
    </div>
  )
}

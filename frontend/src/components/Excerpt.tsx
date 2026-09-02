import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import { REDACTION_MARKER } from '../api'
import { markdownComponents } from '../markdown'

// The retrieved protocol text is Markdown (the two pdfplumber-recovered sections
// carry real tables). Render it through the same setup as the answer text, plus
// remark-breaks — unlike Claude's prose, the raw excerpts rely on single
// newlines to separate bulleted lines, which plain Markdown would collapse.
//
// The [REDACTED: ...] marker can sit anywhere — including inside a table cell —
// so we can't just split the string without breaking the table. Instead swap it
// for a sentinel wrapped in backticks: Markdown parses that as an inline code
// node (valid mid-table), and the `code` renderer below turns the sentinel into
// the amber badge. Anything else stays a normal code span.
const SENTINEL = 'cci-redacted-marker'

export function Excerpt({ text }: { text: string }) {
  const prepared = text.split(REDACTION_MARKER).join(`\`${SENTINEL}\``)
  return (
    <div className="space-y-2 text-[13px] leading-relaxed text-ink-soft">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={{
          ...markdownComponents,
          code: ({ children }) =>
            String(children) === SENTINEL ? (
              <RedactionBadge />
            ) : (
              <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[12px]">
                {children}
              </code>
            ),
        }}
      >
        {prepared}
      </ReactMarkdown>
    </div>
  )
}

function RedactionBadge() {
  return (
    <span className="mx-0.5 inline-block rounded bg-amber-100 px-1.5 py-0.5 font-sans text-[11px] font-semibold tracking-wide text-amber-800 uppercase ring-1 ring-amber-300">
      redacted — commercially confidential
    </span>
  )
}

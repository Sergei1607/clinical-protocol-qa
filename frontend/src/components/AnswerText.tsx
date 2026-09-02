import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

// Claude returns lightly-formatted Markdown (bold labels, bullet lists, the odd
// table). Render it, but keep the styling restrained so it reads as a written
// answer, not a document.
export function AnswerText({ text }: { text: string }) {
  return (
    <div className="space-y-3 text-[15px] leading-relaxed text-ink">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p>{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
          ul: ({ children }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
          li: ({ children }) => <li className="marker:text-slate-400">{children}</li>,
          h1: ({ children }) => <p className="font-semibold text-ink">{children}</p>,
          h2: ({ children }) => <p className="font-semibold text-ink">{children}</p>,
          h3: ({ children }) => <p className="font-semibold text-ink">{children}</p>,
          code: ({ children }) => (
            <code className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[13px]">{children}</code>
          ),
          a: ({ children }) => <span className="text-ink">{children}</span>,
          table: ({ children }) => (
            <div className="overflow-x-auto">
              <table className="my-1 border-collapse text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-slate-300 bg-slate-50 px-2 py-1 text-left font-semibold">
              {children}
            </th>
          ),
          td: ({ children }) => <td className="border border-slate-200 px-2 py-1 align-top">{children}</td>,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}

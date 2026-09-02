import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { markdownComponents } from '../markdown'

// Claude returns lightly-formatted Markdown (bold labels, bullet lists, the odd
// table). Render it, but keep the styling restrained so it reads as a written
// answer, not a document.
export function AnswerText({ text }: { text: string }) {
  return (
    <div className="space-y-3 text-[15px] leading-relaxed text-ink">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {text}
      </ReactMarkdown>
    </div>
  )
}

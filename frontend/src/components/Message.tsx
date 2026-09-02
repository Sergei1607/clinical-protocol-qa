import type { Source } from '../api'
import { AnswerText } from './AnswerText'
import { Sources } from './Sources'

export type ChatMessage =
  | { role: 'user'; text: string }
  | { role: 'assistant'; text: string; sources: Source[]; model: string }
  | { role: 'pending' }
  | { role: 'error'; text: string }

export function Message({ msg }: { msg: ChatMessage }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-accent px-4 py-2.5 text-[15px] text-white">
          {msg.text}
        </div>
      </div>
    )
  }

  if (msg.role === 'pending') {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <span className="flex gap-1">
          <Dot /> <Dot delay="150ms" /> <Dot delay="300ms" />
        </span>
        searching the protocol…
      </div>
    )
  }

  if (msg.role === 'error') {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        Couldn’t get an answer: {msg.text}
      </div>
    )
  }

  return (
    <div>
      <AnswerText text={msg.text} />
      <Sources sources={msg.sources} />
    </div>
  )
}

function Dot({ delay = '0ms' }: { delay?: string }) {
  return (
    <span
      className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400"
      style={{ animationDelay: delay }}
    />
  )
}

import { useEffect, useRef, useState } from 'react'
import { ask } from './api'
import { Message, type ChatMessage } from './components/Message'

const SUGGESTIONS = [
  'What is the primary endpoint of this study?',
  'How should belzutifan dosing be modified if a participant develops hypoxia?',
  'What factors is the randomization stratified by?',
  'What are the tertiary and exploratory objectives of the study?',
]

export default function App() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  async function send(question: string) {
    const q = question.trim()
    if (!q || busy) return
    setInput('')
    setBusy(true)
    setMessages((m) => [...m, { role: 'user', text: q }, { role: 'pending' }])
    try {
      const res = await ask(q)
      setMessages((m) => [
        ...m.slice(0, -1),
        { role: 'assistant', text: res.answer_text, sources: res.sources, model: res.model },
      ])
    } catch (err) {
      setMessages((m) => [
        ...m.slice(0, -1),
        { role: 'error', text: err instanceof Error ? err.message : String(err) },
      ])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col px-4">
      <header className="border-b border-slate-200 py-5">
        <h1 className="text-lg font-semibold text-ink">Clinical Protocol Q&amp;A</h1>
        <p className="mt-0.5 text-sm text-ink-soft">
          Ask about protocol <span className="font-medium">MK-6482-005</span> (belzutifan vs.
          everolimus in advanced RCC). Answers are grounded only in the posted protocol text, with
          the source excerpts shown.
        </p>
      </header>

      <div ref={scrollRef} className="flex-1 space-y-5 overflow-y-auto py-6">
        {messages.length === 0 ? (
          <div className="pt-6">
            <p className="text-sm text-ink-soft">Try one of these:</p>
            <div className="mt-3 flex flex-col items-start gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="rounded-full border border-slate-200 bg-white px-3.5 py-1.5 text-sm text-ink-soft transition-colors hover:border-accent hover:text-accent"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, i) => <Message key={i} msg={msg} />)
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
        className="border-t border-slate-200 py-4"
      >
        <div className="flex items-end gap-2 rounded-xl border border-slate-300 bg-white p-2 focus-within:border-accent">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send(input)
              }
            }}
            rows={1}
            placeholder="Ask a question about the protocol…"
            className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-[15px] text-ink outline-none placeholder:text-slate-400"
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-opacity disabled:opacity-40"
          >
            {busy ? '…' : 'Ask'}
          </button>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          Retrieval-augmented demo · not medical or regulatory advice · portions of the protocol are
          redacted by the sponsor.
        </p>
      </form>
    </div>
  )
}

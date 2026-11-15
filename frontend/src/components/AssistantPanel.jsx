import { useCallback, useRef, useState } from 'react'
import { useApp } from '../context/AppContext'
import { MAX_RECORDING_MS, useRecorder } from '../hooks/useRecorder'
import { playSpeech } from '../lib/audio'
import MessagePreview from './MessagePreview'

export const DEMO_PHRASES = [
  'Agarwal ka payment 7 tareekh ko kar do',
  'Sunita ji ne 650 ka udhaar liya, Friday tak denge',
  'Cash ki kya situation hai?',
  'Kal kitni bikri hui?',
]

export default function AssistantPanel({ suggestions = DEMO_PHRASES, title = 'Vyapar Hub se poochhiye' }) {
  const { api, setTrace, requestApproval, refresh, status } = useApp()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [speakReplies, setSpeakReplies] = useState(true)
  const inputRef = useRef(null)

  const history = () => messages.slice(-10).map((m) => ({ role: m.role, content: m.text }))
  const push = (m) => setMessages((ms) => [...ms, m])

  const handleResult = useCallback(
    async (result, question) => {
      const auto = (result.pending_actions || []).filter((a) => a.status === 'executed')
      push({ role: 'assistant', text: result.reply_text, previews: auto.map((a) => a.payload?.body || a.payload?.messages?.[0]?.body).filter(Boolean) })
      setTrace({ question, reply: result.reply_text, steps: result.tool_trace || [], mode: result.mode })
      requestApproval(result.pending_actions)
      if (auto.length) refresh()
      if (speakReplies) {
        const audio = result.audio || (await api.speak(result.reply_text).catch(() => null))
        playSpeech(audio, result.reply_text)
      }
    },
    [api, refresh, requestApproval, setTrace, speakReplies],
  )

  async function sendText(text) {
    const q = text.trim()
    if (!q || busy) return
    setInput('')
    push({ role: 'user', text: q })
    setBusy(true)
    try {
      await handleResult(await api.chat(q, history()), q)
    } catch (e) {
      push({ role: 'assistant', text: `Maaf kijiye, server se jawab nahi aaya (${e.message}).`, error: true })
    } finally {
      setBusy(false)
    }
  }

  const onRecorded = useCallback(
    async (blob) => {
      setBusy(true)
      try {
        const result = await api.voiceTurn(blob, history())
        if (result.transcript) push({ role: 'user', text: result.transcript, voice: true })
        await handleResult(result, result.transcript || '(voice)')
      } catch (e) {
        const msg = e.status === 503 ? 'Awaaz service abhi uplabdh nahi hai. Type karke likhiye.' : `Awaaz samajh nahi aayi (${e.message}).`
        push({ role: 'assistant', text: msg, error: true })
        inputRef.current?.focus()
      } finally {
        setBusy(false)
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [api, handleResult, messages],
  )
  const rec = useRecorder(onRecorded)
  const voiceOk = rec.supported && status?.voice === 'sarvam'

  return (
    <section className="rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200" aria-label="Assistant">
      <div className="flex items-center justify-between">
        <h2 className="text-[15px] font-semibold text-navy">{title}</h2>
        <label className="flex items-center gap-1 text-[11px] text-slate-600">
          <input type="checkbox" checked={speakReplies} onChange={(e) => setSpeakReplies(e.target.checked)} />
          Jawab bolkar
        </label>
      </div>

      <div className="mt-2 max-h-72 space-y-2 overflow-y-auto" aria-live="polite">
        {messages.length === 0 && <p className="text-sm text-slate-500">Mic dabaakar boliye, ya neeche likhiye.</p>}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-2xl px-3 py-2 text-[14px] leading-snug ${
                m.role === 'user' ? 'rounded-br-sm bg-navy text-white' : m.error ? 'bg-red-50 text-red-900' : 'rounded-bl-sm bg-sky/15 text-navy'
              }`}
            >
              {m.voice && <span className="mr-1" aria-label="spoken">🎙</span>}
              {m.text}
              {m.previews?.map((p, j) => <MessagePreview key={j} body={p} compact />)}
            </div>
          </div>
        ))}
        {busy && <p className="text-xs text-slate-400">Soch raha hoon…</p>}
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5">
        {suggestions.map((s) => (
          <button key={s} onClick={() => sendText(s)} disabled={busy} className="rounded-full bg-slate-100 px-2.5 py-1 text-[12px] text-navy hover:bg-sky/20 disabled:opacity-50">
            {s}
          </button>
        ))}
      </div>

      <form
        className="mt-3 flex items-center gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          sendText(input)
        }}
      >
        {voiceOk && (
          <button
            type="button"
            onClick={rec.recording ? rec.stop : rec.start}
            disabled={busy && !rec.recording}
            aria-label={rec.recording ? 'Stop recording' : 'Start voice command'}
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-xl text-white shadow ${rec.recording ? 'animate-pulse bg-red-600' : 'bg-sky'}`}
          >
            {rec.recording ? '■' : '🎙'}
          </button>
        )}
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={rec.recording ? `Sun raha hoon… ${Math.ceil((MAX_RECORDING_MS - rec.elapsed) / 1000)}s` : 'Likhiye… (Hindi / Hinglish)'}
          className="min-w-0 flex-1 rounded-full bg-slate-100 px-4 py-3 text-[14px] outline-none focus:ring-2 focus:ring-sky"
          aria-label="Message"
        />
        <button type="submit" disabled={busy || !input.trim()} className="rounded-full bg-navy px-4 py-3 text-sm font-semibold text-white disabled:opacity-40">
          Bhejo
        </button>
      </form>
      {rec.error && <p className="mt-1 text-xs text-red-700">{rec.error}</p>}
      {!voiceOk && <p className="mt-1 text-[11px] text-slate-500">Voice off (no Sarvam key or no mic): typed input mode.</p>}
    </section>
  )
}

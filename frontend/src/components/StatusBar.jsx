import { useApp } from '../context/AppContext'

function Pill({ on, label, title }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 ring-1 ${on ? 'bg-emerald-50 text-emerald-800 ring-emerald-200' : 'bg-amber-50 text-amber-800 ring-amber-200'}`}>
      <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${on ? 'bg-emerald-500' : 'bg-amber-500'}`} />
      {label}
    </span>
  )
}

// Shows which mode each external service runs in, plus the demo clock and the synthetic-data badge.
export default function StatusBar() {
  const { status } = useApp()
  if (!status) {
    return <div className="bg-red-50 px-3 py-1 text-[11px] text-red-800" role="status">Backend offline</div>
  }
  const llm = { groq: 'Groq', grok: 'Grok', fallback: 'Rule-based' }[status.llm] || status.llm
  const now = new Date(status.now)
  return (
    <div className="flex flex-wrap items-center gap-1.5 bg-white px-3 py-1.5 text-[11px] font-medium" role="status" aria-label="Service modes">
      <Pill on={status.llm !== 'fallback'} label={`AI: ${llm}`} title={status.llm_model} />
      <Pill on={status.voice === 'sarvam'} label={status.voice === 'sarvam' ? 'Voice: Sarvam' : 'Voice: browser'} />
      <Pill on={false} label="Msgs: preview" title="Customer messages are shown as previews; nothing is sent" />
      <span className="ml-auto rounded-full bg-navy px-2 py-0.5 text-white" title="Every number here is generated, not real">
        Demo data
      </span>
      <span className="w-full text-[10px] text-slate-500">
        Demo clock: {now.toLocaleString('en-IN', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
      </span>
    </div>
  )
}

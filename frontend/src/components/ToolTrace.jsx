import { useState } from 'react'
import { useApp } from '../context/AppContext'

const SOURCE = {
  groq: 'bg-violet-50 text-violet-800',
  grok: 'bg-violet-50 text-violet-800',
  llm: 'bg-violet-50 text-violet-800',
  'rule-based': 'bg-amber-50 text-amber-800',
  guard: 'bg-red-50 text-red-800',
}

function Step({ step }) {
  const [open, setOpen] = useState(false)
  const r = step.result || {}
  return (
    <li className="rounded-xl bg-white p-3 ring-1 ring-slate-200">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded bg-navy px-1.5 py-0.5 font-mono text-white">{step.step}</span>
        <code className="font-semibold text-navy">{step.tool}</code>
        <span className={`rounded px-1.5 py-0.5 ${SOURCE[step.source] || 'bg-slate-100'}`}>{step.source}</span>
        <span className="ml-auto text-slate-500">{step.ms} ms</span>
      </div>
      {Object.keys(step.args || {}).length > 0 && (
        <p className="mt-1 font-mono text-[11px] text-slate-600">args: {JSON.stringify(step.args)}</p>
      )}
      {r.speak && <p className="mt-1 text-[13px] text-slate-800">“{r.speak}”</p>}
      {r.error && <p className="mt-1 text-[12px] text-red-700">error: {r.error} {r.detail || ''}</p>}
      {r.ungrounded_numbers && (
        <p className="mt-1 text-[12px] text-red-700">Number guard: {r.ungrounded_numbers.join(', ')} not found in any tool result → reply replaced.</p>
      )}
      <button onClick={() => setOpen((o) => !o)} className="mt-1 text-[11px] font-semibold text-sky-700">
        {open ? 'Hide raw result' : 'Show raw result'}
      </button>
      {open && <pre className="mt-1 max-h-60 overflow-auto rounded bg-slate-50 p-2 text-[10px]">{JSON.stringify(r, null, 2)}</pre>}
    </li>
  )
}

// "How I got this": proves every number in the reply came from a tool call.
export default function ToolTrace({ defaultOpen = false }) {
  const { trace } = useApp()
  const [open, setOpen] = useState(defaultOpen)
  return (
    <section className="rounded-2xl bg-slate-50 p-4 ring-1 ring-slate-200">
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center justify-between text-left" aria-expanded={open}>
        <span className="font-semibold text-navy">How I got this</span>
        <span className="text-xs text-slate-500">{trace ? `${trace.steps.length} step${trace.steps.length === 1 ? '' : 's'}` : 'no question yet'} {open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="mt-3">
          {!trace ? (
            <p className="text-sm text-slate-500">Assistant se kuch poochhiye: har jawab ke tool calls yahan dikhenge.</p>
          ) : (
            <>
              <p className="text-xs text-slate-500">Q: “{trace.question}” · mode: {trace.mode}</p>
              <p className="mt-1 text-xs text-slate-600">
                Rule: the AI may only say numbers that appear in these tool results. The server checks every reply.
              </p>
              {trace.steps.length === 0 ? (
                <p className="mt-2 text-sm text-slate-500">No tools were needed for this reply.</p>
              ) : (
                <ol className="mt-2 space-y-2">
                  {trace.steps.map((s) => (
                    <Step key={`${s.step}-${s.tool}`} step={s} />
                  ))}
                </ol>
              )}
            </>
          )}
        </div>
      )}
    </section>
  )
}

import { useApp, useLoad } from '../context/AppContext'
import { ErrorNote, Loading } from './Card'

// Subah ki Report: the same three items the Soundbox reads out, plus one suggestion.
export default function BriefingCard() {
  const { api, say, soundbox } = useApp()
  const { data, error, loading } = useLoad(() => api.briefing())
  return (
    <section className="rounded-2xl bg-gradient-to-br from-navy to-[#0a4a9e] p-4 text-white shadow-md">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] uppercase tracking-wider text-sky-200">Subah ki Report</p>
          <h2 className="text-lg font-semibold">Aaj ka hisaab</h2>
        </div>
        <button
          onClick={() => data && say({ text: data.spoken_text })}
          disabled={!data || soundbox.playing}
          className="flex items-center gap-1 rounded-full bg-sky px-4 py-2 text-sm font-bold text-navy disabled:opacity-60"
          aria-label="Play morning briefing"
        >
          ▶ Suno
        </button>
      </div>
      {loading && !data && <Loading />}
      <ErrorNote error={error} />
      {data && (
        <>
          <div className="mt-3 grid grid-cols-3 gap-2">
            {data.cards.map((c) => (
              <div key={c.kind} className="rounded-xl bg-white/10 p-2.5">
                <p className="text-[11px] text-sky-100">{c.title}</p>
                <p className="text-[17px] font-semibold">{c.value}</p>
                {c.kind === 'sales' && c.vs_usual_pct != null && (
                  <p className="text-[11px] text-sky-100">
                    {c.vs_usual_pct >= 0 ? '▲' : '▼'} {Math.abs(c.vs_usual_pct)}% vs usual
                  </p>
                )}
                {c.kind !== 'sales' && <p className="text-[11px] text-sky-100">{c.count} {c.kind === 'payments' ? 'payment' : 'log'}</p>}
              </div>
            ))}
          </div>
          <p className="mt-3 rounded-xl bg-white/10 p-2.5 text-[13px] leading-snug">💡 {data.suggestion.text}</p>
        </>
      )}
    </section>
  )
}

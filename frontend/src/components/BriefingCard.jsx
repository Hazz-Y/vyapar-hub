import { useApp, useLoad } from '../context/AppContext'
import { ErrorNote, Loading } from './Card'

// Subah ki Report: the same three items the Soundbox reads out, plus one suggestion.
export default function BriefingCard() {
  const { api, say, soundbox } = useApp()
  const { data, error, loading } = useLoad(() => api.briefing())

  function playBriefing() {
    if (!data) return
    api.display(
      'AAJ KA HISAAB',
      data.cards[0]?.value || 'Rs 16,408',
      'Kal Ki Bikri: +3%',
      `Due: ${data.cards[1]?.value} | Udh: ${data.cards[2]?.value}`,
    ).catch(() => {})
    say({ text: data.spoken_text })
  }

  function clickTile(c) {
    if (c.kind === 'sales') {
      api.display('KAL KI BIKRI', c.value, 'Aam Saturday se 3% up', 'Paytm Soundbox').catch(() => {})
    } else if (c.kind === 'payments') {
      api.display('AAJ KE PAYMENT', c.value, `${c.count} Payment Due`, 'Sharma Milk Dairy').catch(() => {})
    } else if (c.kind === 'udhaar') {
      api.display('UDHAAR VASOOLI', c.value, `${c.count} Log Baaki`, 'Anita ji, Manoj ji').catch(() => {})
    }
  }

  return (
    <section className="rounded-2xl bg-gradient-to-br from-navy to-[#0a4a9e] p-4 text-white shadow-md">
      <div className="flex items-center justify-between">
        <div onClick={playBriefing} className="cursor-pointer">
          <p className="text-[11px] uppercase tracking-wider text-sky-200">Subah ki Report</p>
          <h2 className="text-lg font-semibold hover:text-sky-100">Aaj ka hisaab</h2>
        </div>
        <button
          onClick={playBriefing}
          disabled={!data || soundbox.playing}
          className="flex items-center gap-1 rounded-full bg-sky px-4 py-2 text-sm font-bold text-navy hover:bg-sky-200 active:scale-95 disabled:opacity-60 cursor-pointer"
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
              <div
                key={c.kind}
                onClick={() => clickTile(c)}
                className="cursor-pointer rounded-xl bg-white/10 p-2.5 transition hover:bg-white/20 active:scale-95"
              >
                <p className="text-[11px] text-sky-100">{c.title}</p>
                <p className="text-[17px] font-semibold">{c.value}</p>
                {c.kind === 'sales' && c.vs_usual_pct != null && (
                  <p className="text-[11px] text-sky-100">
                    {c.vs_usual_pct >= 0 ? '▲' : '▼'} {Math.abs(c.vs_usual_pct)}% vs usual
                  </p>
                )}
                {c.kind !== 'sales' && (
                  <p className="text-[11px] text-sky-100">
                    {c.count} {c.kind === 'payments' ? 'payment' : 'log'}
                  </p>
                )}
              </div>
            ))}
          </div>
          <p className="mt-3 rounded-xl bg-white/10 p-2.5 text-[13px] leading-snug">💡 {data.suggestion.text}</p>
        </>
      )}
    </section>
  )
}

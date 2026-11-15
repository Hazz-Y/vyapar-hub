import { useState } from 'react'
import AssistantPanel from '../components/AssistantPanel'
import Card, { Button, ErrorNote, Loading } from '../components/Card'
import Heatmap from '../components/Heatmap'
import MessagePreview from '../components/MessagePreview'
import { useApp, useLoad } from '../context/AppContext'
import { rupees, shortDate } from '../lib/format'
import { StatTile } from './CashRadar'

const GROWTH_PHRASES = ['Kaun se grahak nahi aa rahe?', 'Win-back offer bhejo', 'Sabse zyada bikri kab hoti hai?']

function LapsedCard({ lapsed }) {
  const { api, requestApproval, refresh } = useApp()
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const [result, setResult] = useState(null)

  async function winback() {
    setBusy(true)
    setErr(null)
    try {
      const r = await api.draftWinback(10)
      setResult(r)
      requestApproval(r.pending_actions)
      if (!r.needs_approval) refresh()
    } catch (e) {
      setErr(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title={`${lapsed.count} regulars 3 hafte se nahi aaye`}>
      <p className="text-[12px] text-slate-600">
        {lapsed.opted_in_count} ne offers ke liye haan kaha hai. Offer sirf unhi ko jayega.
      </p>
      <ul className="mt-2 divide-y divide-slate-100">
        {lapsed.customers.slice(0, 6).map((c) => (
          <li key={c.customer_id} className="flex items-center justify-between gap-2 py-1.5 text-[13px]">
            <span className="min-w-0 truncate font-medium text-navy">{c.name}</span>
            <span className="shrink-0 text-[11px] text-slate-500">
              {c.days_since} din · {shortDate(c.last_visit)}
              {!c.opted_in && <span className="ml-1 rounded-full bg-slate-100 px-1.5 text-slate-500">no consent</span>}
            </span>
          </li>
        ))}
      </ul>
      {lapsed.customers.length > 6 && <p className="text-[11px] text-slate-400">+{lapsed.customers.length - 6} aur</p>}
      <ErrorNote error={err} />
      <Button variant="sky" className="mt-3 w-full" onClick={winback} disabled={busy || !lapsed.opted_in_count}>
        {busy ? 'Ban raha hai…' : `🎁 ${lapsed.opted_in_count} grahakon ko 10% offer bhejo`}
      </Button>
      {result?.message_preview && (
        <div className="mt-2">
          <p className="text-[11px] text-slate-500">{result.speak}</p>
          <MessagePreview body={result.message_preview} to={`${result.recipients} grahak`} />
        </div>
      )}
    </Card>
  )
}

function SlowDays({ slow }) {
  const max = Math.max(1, ...slow.by_weekday.map((d) => d.avg_sales))
  return (
    <Card title="Hafte ke din">
      <ul className="space-y-1.5" aria-label="Average sales by weekday">
        {slow.by_weekday.map((d) => {
          const tag = d.weekday_name === slow.slowest.weekday_name ? 'slowest' : d.weekday_name === slow.busiest.weekday_name ? 'busiest' : null
          return (
            <li key={d.weekday} className="flex items-center gap-2 text-[12px]">
              <span className="w-9 shrink-0 text-slate-600">{d.weekday_name.slice(0, 3)}</span>
              <span className="h-3 flex-1 rounded-r bg-slate-100">
                <span
                  className="block h-3 rounded-r"
                  style={{ width: `${(100 * d.avg_sales) / max}%`, backgroundColor: tag === 'slowest' ? '#94a3b8' : '#002E6E' }}
                />
              </span>
              <span className="w-28 shrink-0 text-right text-slate-700">
                {rupees(d.avg_sales)}{' '}
                <span className="text-slate-500">
                  ({d.vs_avg_pct > 0 ? '+' : ''}
                  {d.vs_avg_pct}%)
                </span>
              </span>
            </li>
          )
        })}
      </ul>
      <p className="mt-2 text-[11px] text-slate-500">
        Sabse dheema: {slow.slowest.weekday_name} ({slow.slowest.below_avg_pct}% kam). Sabse tez: {slow.busiest.weekday_name}. Average{' '}
        {rupees(slow.overall_avg)}/din, pichhle {slow.weeks} hafte.
      </p>
    </Card>
  )
}

export default function Growth() {
  const { api } = useApp()
  const { data: g, loading, error } = useLoad(() => api.growth())

  return (
    <div className="space-y-4 p-4 pb-6">
      <h1 className="text-[17px] font-semibold text-navy">Growth</h1>
      {loading && !g && <Loading />}
      <ErrorNote error={error} />

      {g && (
        <>
          {g.lapsed_regulars?.count > 0 && <LapsedCard lapsed={g.lapsed_regulars} />}

          <Card title="Kab sabse zyada bikri hoti hai">
            <p className="mb-2 text-[12px] text-slate-600">
              Peak: <b className="text-navy">{g.peak_hours.peak_slot.label}</b> ({rupees(g.peak_hours.peak_slot.avg_sales)} avg)
            </p>
            <Heatmap cells={g.peak_hours.cells} hours={g.peak_hours.hours} />
          </Card>

          <SlowDays slow={g.slow_days} />

          {g.festival && (
            <Card title={`${g.festival.festival}: is saal vs pichhle saal`}>
              <div className="flex gap-2">
                <StatTile label={`${shortDate(g.festival.this_year.start)} – ${shortDate(g.festival.this_year.end)}`} value={rupees(g.festival.this_year.total)} sub="is saal" tone={g.festival.change_pct >= 0 ? 'good' : 'plain'} />
                <StatTile label={`${shortDate(g.festival.last_year.start)} – ${shortDate(g.festival.last_year.end)}`} value={rupees(g.festival.last_year.total)} sub="pichhle saal" />
              </div>
              <p className="mt-2 text-[12px] text-slate-600">
                {g.festival.change_pct >= 0 ? '▲' : '▼'} {Math.abs(g.festival.change_pct)}% ({rupees(g.festival.change_abs)}) · {g.festival.days} din ka festival season
              </p>
            </Card>
          )}

          {g.summary_text && <p className="rounded-xl bg-white px-3 py-2.5 text-[13px] text-slate-700 ring-1 ring-slate-200">{g.summary_text}</p>}
        </>
      )}

      <AssistantPanel suggestions={GROWTH_PHRASES} title="Growth ke baare mein poochhiye" />
    </div>
  )
}

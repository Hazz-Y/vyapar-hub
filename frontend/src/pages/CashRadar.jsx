import { useState } from 'react'
import AssistantPanel from '../components/AssistantPanel'
import Card, { Button, ErrorNote, Loading } from '../components/Card'
import RadarChart from '../components/RadarChart'
import { useApp, useLoad } from '../context/AppContext'
import { rupees, shortDate } from '../lib/format'

const CASH_PHRASES = ['Agarwal ka payment 7 tareekh ko kar do', 'Cash ki kya situation hai?', 'Agle hafte kitne bill hain?']

export function StatTile({ label, value, sub, tone = 'plain' }) {
  const tones = { plain: 'bg-white ring-slate-200', critical: 'bg-red-50 ring-red-200', good: 'bg-emerald-50 ring-emerald-200' }
  return (
    <div className={`min-w-0 flex-1 rounded-2xl p-3 ring-1 ${tones[tone]}`}>
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className={`mt-0.5 text-[17px] font-semibold ${tone === 'critical' ? 'text-[#d03b3b]' : 'text-navy'}`}>{value}</p>
      {sub && <p className="mt-0.5 text-[11px] leading-tight text-slate-500">{sub}</p>}
    </div>
  )
}

function ShortfallCard({ sf, onFix, busy }) {
  return (
    <section className="rounded-2xl bg-red-50 p-4 ring-1 ring-red-200" aria-label="Cash shortfall">
      <p className="flex items-center gap-1.5 text-[13px] font-semibold text-[#d03b3b]">
        <span aria-hidden>⚠</span> Kami: {sf.date_text}
      </p>
      <p className="mt-1 text-[13px] text-red-900">
        Balance {rupees(sf.lowest_balance_p10)} tak gir sakta hai, buffer se {rupees(sf.gap)} kam.
      </p>
      {sf.cause && (
        <p className="mt-1 text-[12px] text-slate-700">
          Wajah: {sf.cause.supplier} ka {rupees(sf.cause.amount)} bill, {shortDate(sf.cause.due_date)} ko.
        </p>
      )}
      {sf.fix ? (
        <div className="mt-3 rounded-xl bg-white p-3 ring-1 ring-red-100">
          <p className="text-[13px] text-navy">💡 {sf.fix.text}</p>
          <Button className="mt-2 w-full" onClick={() => onFix(sf.fix)} disabled={busy}>
            {busy ? 'Ban raha hai…' : `${sf.fix.move_to_text} ko shift karein`}
          </Button>
        </div>
      ) : (
        <p className="mt-2 text-[12px] text-slate-600">Koi ek bill shift karke yeh kami door nahi hoti. Assistant se baat karein.</p>
      )}
    </section>
  )
}

export default function CashRadar() {
  const { api, requestApproval } = useApp()
  const [preview, setPreview] = useState(false)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const { data: radar, loading, error } = useLoad(() => api.radar())
  const fix = radar?.shortfalls?.[0]?.fix
  const whatIf = useLoad(
    () => (preview && fix ? api.radar({ move_payable_id: fix.payable_id, move_to: fix.move_to }) : Promise.resolve(null)),
    [preview, fix?.payable_id, fix?.move_to],
  )
  const { data: backtest } = useLoad(() => api.backtest())

  async function draftFix(f) {
    setBusy(true)
    setErr(null)
    try {
      const r = await api.draftReschedule(f.payable_id, f.move_to)
      requestApproval(r.pending_actions)
    } catch (e) {
      setErr(e)
    } finally {
      setBusy(false)
    }
  }

  const shown = preview && whatIf.data ? whatIf.data : radar
  const sf = radar?.shortfalls?.[0]

  return (
    <div className="space-y-4 p-4 pb-6">
      <h1 className="text-[17px] font-semibold text-navy">Cash Radar</h1>
      {loading && !radar && <Loading label="Forecast ban raha hai…" />}
      <ErrorNote error={error || err} />

      {radar && (
        <>
          <div className="flex gap-2">
            <StatTile label="Abhi balance" value={radar.balance_now_text} />
            <StatTile label="Buffer" value={rupees(radar.buffer)} sub="kam se kam itna rakhein" />
            {sf ? (
              <StatTile label="Pehli kami" value={shortDate(sf.date)} sub={`${sf.days_ahead} din baad`} tone="critical" />
            ) : (
              <StatTile label={`${radar.horizon_days} din`} value="✓ Safe" sub="buffer se upar" tone="good" />
            )}
          </div>

          {sf && <ShortfallCard sf={sf} onFix={draftFix} busy={busy} />}

          <Card
            title={`Agle ${radar.horizon_days} din ka balance`}
            action={
              fix && (
                <label className="flex items-center gap-1 text-[11px] text-slate-600">
                  <input type="checkbox" checked={preview} onChange={(e) => setPreview(e.target.checked)} />
                  Fix ke baad
                </label>
              )
            }
          >
            {preview && whatIf.loading && !whatIf.data ? (
              <Loading />
            ) : (
              <RadarChart days={shown.days} shortfalls={shown.shortfalls} buffer={shown.buffer} />
            )}
            {preview && whatIf.data && (
              <p className="mt-1 text-[11px] text-emerald-800">Preview: bill shift karne ke baad (abhi approve nahi hua).</p>
            )}
            <p className="mt-2 text-[11px] text-slate-500">{radar.method}</p>
          </Card>

          {!sf && <p className="rounded-xl bg-white px-3 py-2.5 text-[13px] text-slate-700 ring-1 ring-slate-200">{radar.summary_text}</p>}
        </>
      )}

      {backtest && (
        <Card title="Forecast kitna sahi hai?">
          <div className="flex gap-2">
            <StatTile label="Model ki galti (MAE)" value={rupees(backtest.model.mae)} sub="per din" tone={backtest.beats_baseline ? 'good' : 'plain'} />
            <StatTile label={`Baseline: ${backtest.baseline_name}`} value={rupees(backtest.baseline.mae)} sub="per din" />
          </div>
          <p className="mt-2 text-[11px] text-slate-500">
            Pichhle {backtest.window_days} din par jaancha: model baseline se {backtest.mae_improvement_pct}% behtar.
          </p>
        </Card>
      )}

      <AssistantPanel suggestions={CASH_PHRASES} title="Cash ke baare mein poochhiye" />
    </div>
  )
}

import { useState } from 'react'
import { useApp, useLoad } from '../context/AppContext'
import Card, { Loading, ErrorNote, Button } from '../components/Card'
import AssistantPanel from '../components/AssistantPanel'
import { rupees, shortDate } from '../lib/format'

const SUP_PHRASES = [
  'Agarwal ka payment 7 tareekh ko kar do',
  'Upcoming payments kya hain?',
  'Sharma Dairy ka payment kab hai?',
]

function PayableRow({ p, onPay, onReschedule }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const daysUntil = p.days_to_due ?? null

  async function pay() {
    setBusy(true)
    setErr(null)
    try { await onPay(p.id) } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  async function reschedule() {
    setBusy(true)
    setErr(null)
    try { await onReschedule(p.id) } catch (e) { setErr(e.message) } finally { setBusy(false) }
  }

  const urgent = daysUntil !== null && daysUntil <= 2

  return (
    <div className={`rounded-2xl p-3 ring-1 ${urgent ? 'bg-amber-50 ring-amber-200' : 'bg-white ring-slate-200'}`}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[14px] font-semibold text-navy truncate">{p.supplier}</p>
          <p className="text-[12px] text-slate-500">
            Due: {p.due_date ? shortDate(p.due_date) : '—'}
            {daysUntil !== null && (
              <span className={`ml-2 ${urgent ? 'font-semibold text-amber-700' : ''}`}>
                {daysUntil === 0 ? 'aaj' : daysUntil < 0 ? `${Math.abs(daysUntil)}d late` : `${daysUntil}d baaki`}
              </span>
            )}
          </p>
          {p.invoice_no && <p className="text-[11px] text-slate-400">Invoice: {p.invoice_no}</p>}
        </div>
        <p className="text-[16px] font-semibold text-navy shrink-0">{rupees(p.amount)}</p>
      </div>
      {err && <p className="mt-1 text-[11px] text-red-700">{err}</p>}
      <div className="mt-2 flex gap-2">
        <Button variant="primary" className="flex-1 text-[12px]" onClick={pay} disabled={busy || p.status === 'paid'}>
          💸 Pay
        </Button>
        <Button variant="ghost" className="flex-1 text-[12px]" onClick={reschedule} disabled={busy || p.status === 'paid'}>
          📅 Reschedule
        </Button>
      </div>
    </div>
  )
}

export default function Suppliers() {
  const { api, requestApproval, status } = useApp()
  const [showAll, setShowAll] = useState(false)
  const { data: payables, loading, error } = useLoad(() => api.payables('upcoming'))
  const { data: matching } = useLoad(() => api.matching())
  const [matchOpen, setMatchOpen] = useState(false)

  // GST export defaults to the last full month on the demo clock.
  const demoNow = status?.now ? new Date(status.now) : new Date()
  const lastMonth = new Date(demoNow.getFullYear(), demoNow.getMonth() - 1, 1)
  const gstMonth = `${lastMonth.getFullYear()}-${String(lastMonth.getMonth() + 1).padStart(2, '0')}`

  async function handlePay(id) {
    const r = await api.draftPay(id)
    requestApproval(r.pending_actions || [])
  }

  async function handleReschedule(id) {
    const r = await api.draftReschedule(id, null)
    requestApproval(r.pending_actions || [])
  }

  const upcoming = (payables || []).filter((p) => p.status !== 'paid')
  const visible = showAll ? upcoming : upcoming.slice(0, 8)

  return (
    <div className="space-y-4 p-4 pb-6">
      <h1 className="text-[17px] font-semibold text-navy">Suppliers</h1>


      {/* Payables list */}
      <Card title={`Aane wale bills (${upcoming.length})`}>
        {loading && !payables && <Loading />}
        <ErrorNote error={error} />
        <div className="space-y-3 mt-2">
          {upcoming.length === 0 && !loading && (
            <p className="py-4 text-center text-sm text-slate-400">Koi pending payment nahi.</p>
          )}
          {visible.map((p) => (
            <PayableRow
              key={p.id}
              p={p}
              onPay={handlePay}
              onReschedule={handleReschedule}
            />
          ))}
          {upcoming.length > visible.length && (
            <button onClick={() => setShowAll(true)} className="text-[12px] font-semibold text-sky-700">
              Sab {upcoming.length} dikhao
            </button>
          )}
        </div>
      </Card>

      {/* GST export */}
      <Card title="GST Export">
        <p className="text-[12px] text-slate-600 mb-2">Monthly GSTR-ready CSV download</p>
        <a
          href={api.gstExportUrl(gstMonth)}
          download
          className="inline-flex items-center gap-1.5 rounded-full bg-navy px-4 py-2 text-sm font-semibold text-white"
        >
          ⬇ GST CSV — {gstMonth}
        </a>
      </Card>

      {/* Matching table (collapsed) */}
      {matching && (
        <Card title="Ledger Matching">
          <button
            onClick={() => setMatchOpen((o) => !o)}
            className="text-[12px] font-semibold text-sky-700 hover:underline"
          >
            {matchOpen ? '▲ Hide' : `▼ Show (${matching.matched_fuzzy + matching.matched_llm} of ${matching.distinct_counterparties} names matched)`}
          </button>
          {matchOpen && (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-[11px]">
                <thead>
                  <tr className="border-b border-slate-200 text-left text-slate-500">
                    <th className="px-2 py-1 font-medium">Transaction</th>
                    <th className="px-2 py-1 font-medium">Supplier</th>
                    <th className="px-2 py-1 font-medium text-right">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {matching.rows.slice(0, 20).map((row, i) => (
                    <tr key={i} className="border-b border-slate-100 last:border-0">
                      <td className="px-2 py-1 text-slate-700 max-w-[120px] truncate">{row.counterparty}</td>
                      <td className="px-2 py-1 text-navy font-medium">{row.supplier || '—'}</td>
                      <td className="px-2 py-1 text-right text-slate-500">{row.method === 'llm' ? 'AI' : row.score ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {matching.unmatched > 0 && (
                <p className="mt-2 text-[11px] text-amber-700">{matching.unmatched} names unmatched</p>
              )}
            </div>
          )}
        </Card>
      )}

      <AssistantPanel suggestions={SUP_PHRASES} title="Supplier ke baare mein poochhiye" />
    </div>
  )
}

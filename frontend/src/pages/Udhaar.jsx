import { useState } from 'react'
import { useApp, useLoad } from '../context/AppContext'
import Card, { Loading, ErrorNote, Button } from '../components/Card'
import MessagePreview from '../components/MessagePreview'
import AssistantPanel from '../components/AssistantPanel'
import { rupees, shortDate, STATUS_CHIP } from '../lib/format'

const UDHAAR_PHRASES = [
  'Sunita ji ne 650 ka udhaar liya, Friday tak denge',
  'Kitna udhaar baaki hai?',
  'Sunita ko reminder bhejo',
]

const EMPTY_FORM = { customer_name: '', amount: '', phone: '', due_date: '' }

function StatusChip({ status }) {
  const today = new Date().toISOString().slice(0, 10)
  // Determine effective status: if open but past due, treat as overdue
  const chip = STATUS_CHIP[status] || STATUS_CHIP.open
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${chip.cls}`}>
      {chip.label}
    </span>
  )
}

function UdhaarRow({ entry, onRemind, onSimulate }) {
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  async function remind() {
    setBusy(true)
    setErr(null)
    try {
      const r = await onRemind(entry.id)
      if (r?.message_preview) setPreview(r.message_preview)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function simulate() {
    setBusy(true)
    setErr(null)
    try {
      await onSimulate(entry)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="rounded-2xl bg-white p-3 ring-1 ring-slate-200 space-y-2">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[14px] font-semibold text-navy">{entry.customer_name || entry.name || '—'}</p>
          <p className="text-[12px] text-slate-500">
            Due: {entry.due_date ? shortDate(entry.due_date) : '—'}
            {entry.phone && <span className="ml-2">{entry.phone}</span>}
          </p>
        </div>
        <div className="flex flex-col items-end gap-1 shrink-0">
          <p className="text-[16px] font-semibold text-navy">{rupees(entry.amount)}</p>
          <StatusChip status={entry.status} />
        </div>
      </div>

      {err && <p className="text-[11px] text-red-700" role="alert">{err}</p>}
      {preview && <MessagePreview body={preview.body} to={preview.to} compact />}

      {entry.status !== 'settled' && (
        <div className="flex gap-2 pt-1">
          <Button variant="ghost" className="flex-1 text-[12px]" onClick={remind} disabled={busy}>
            📨 Remind
          </Button>
          <Button variant="sky" className="flex-1 text-[12px]" onClick={simulate} disabled={busy}>
            ✓ Payment mila
          </Button>
        </div>
      )}
    </div>
  )
}

export default function Udhaar() {
  const { api, say, requestApproval, refresh } = useApp()
  const { data, loading, error, reload } = useLoad(() => api.udhaar())
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState(EMPTY_FORM)
  const [addBusy, setAddBusy] = useState(false)
  const [addErr, setAddErr] = useState(null)

  const entries = data || []
  const openEntries = entries.filter((e) => e.status !== 'settled')
  const totalOpen = openEntries.reduce((s, e) => s + (e.amount || 0), 0)
  const overdueCount = openEntries.filter((e) => e.status === 'overdue').length

  async function handleRemind(id) {
    const r = await api.remind(id)
    requestApproval(r.pending_actions || [])
    reload()
    return r
  }

  async function handleSimulate(entry) {
    const r = await api.simulatePayment(entry.amount, entry.customer_name || entry.name)
    if (r.soundbox_text) say({ text: r.soundbox_text, eventId: r.soundbox_event_id })
    reload()
    refresh()
  }

  async function handleAdd(e) {
    e.preventDefault()
    if (!form.customer_name.trim() || !form.amount) return
    setAddBusy(true)
    setAddErr(null)
    try {
      await api.addUdhaar({
        customer_name: form.customer_name.trim(),
        amount: Number(form.amount),
        due_date: form.due_date || null,
        phone: form.phone.trim() || null,
      })
      setForm(EMPTY_FORM)
      setShowAdd(false)
      reload()
    } catch (err) {
      setAddErr(err.message)
    } finally {
      setAddBusy(false)
    }
  }

  return (
    <div className="space-y-4 p-4 pb-6">
      <div className="flex items-center justify-between">
        <h1 className="text-[17px] font-semibold text-navy">Udhaar</h1>
        <Button variant="sky" className="text-[12px]" onClick={() => setShowAdd((s) => !s)}>
          {showAdd ? '✕ Band karo' : '+ Add'}
        </Button>
      </div>

      {/* Totals */}
      <div className="flex gap-3">
        <div className="flex-1 rounded-2xl bg-amber-50 p-3">
          <p className="text-[11px] text-amber-700">Total baaki</p>
          <p className="text-[18px] font-semibold text-navy mt-0.5">{rupees(totalOpen)}</p>
          <p className="text-[11px] text-slate-500">{openEntries.length} log</p>
        </div>
        {overdueCount > 0 && (
          <div className="flex-1 rounded-2xl bg-red-50 p-3">
            <p className="text-[11px] text-[#d03b3b]">Overdue</p>
            <p className="text-[18px] font-semibold text-[#d03b3b] mt-0.5">{overdueCount}</p>
            <p className="text-[11px] text-slate-500">reminder bhejein</p>
          </div>
        )}
      </div>

      {/* Add form */}
      {showAdd && (
        <form onSubmit={handleAdd} className="rounded-2xl bg-white p-4 ring-1 ring-slate-200 space-y-3">
          <p className="text-[13px] font-semibold text-navy">Naya Udhaar</p>
          <input
            required
            placeholder="Grahak ka naam *"
            value={form.customer_name}
            onChange={(e) => setForm((f) => ({ ...f, customer_name: e.target.value }))}
            className="w-full rounded-xl bg-slate-50 px-3 py-2.5 text-[13px] outline-none focus:ring-2 focus:ring-sky"
          />
          <input
            required
            type="number"
            min="1"
            placeholder="Amount (₹) *"
            value={form.amount}
            onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
            className="w-full rounded-xl bg-slate-50 px-3 py-2.5 text-[13px] outline-none focus:ring-2 focus:ring-sky"
          />
          <input
            type="tel"
            placeholder="Phone (optional)"
            value={form.phone}
            onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
            className="w-full rounded-xl bg-slate-50 px-3 py-2.5 text-[13px] outline-none focus:ring-2 focus:ring-sky"
          />
          <input
            type="date"
            placeholder="Due date"
            value={form.due_date}
            onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
            className="w-full rounded-xl bg-slate-50 px-3 py-2.5 text-[13px] outline-none focus:ring-2 focus:ring-sky"
          />
          {addErr && <p className="text-[11px] text-red-700">{addErr}</p>}
          <Button type="submit" variant="primary" disabled={addBusy} className="w-full">
            {addBusy ? 'Save ho raha hai…' : 'Save karein'}
          </Button>
        </form>
      )}

      {loading && !data && <Loading />}
      <ErrorNote error={error} />

      {/* List */}
      <div className="space-y-3">
        {entries.length === 0 && !loading && (
          <p className="py-4 text-center text-sm text-slate-400">Koi udhaar nahi hai.</p>
        )}
        {entries.map((entry) => (
          <UdhaarRow
            key={entry.id}
            entry={entry}
            onRemind={handleRemind}
            onSimulate={handleSimulate}
          />
        ))}
      </div>

      <AssistantPanel suggestions={UDHAAR_PHRASES} title="Udhaar ke baare mein poochhiye" />
    </div>
  )
}

import { useEffect, useState } from 'react'
import { KIND_LABELS, rupees, shortDate } from '../lib/format'
import { playPaytmTune } from '../lib/audio'
import MessagePreview from './MessagePreview'

const PIN_LENGTH = 4
const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', 'clear', '0', 'back']

// Bottom sheet: read-back, amount, recipient and a 4-digit demo PIN pad.
// The PIN is a mock (DEMO_PIN on the server). The app never asks for a real UPI PIN.
export default function ApprovalSheet({ action, onApprove, onReject, onClose }) {
  const [pin, setPin] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null)

  useEffect(() => {
    setPin('')
    setError(null)
    setDone(null)
  }, [action?.id])

  if (!action) return null
  const p = action.payload || {}

  async function submit(code) {
    setBusy(true)
    setError(null)
    try {
      const result = await onApprove(code)
      setDone(result?.confirmation_text || 'Ho gaya.')
    } catch (e) {
      setError(e?.message || 'Approve nahi hua')
      setPin('')
    } finally {
      setBusy(false)
    }
  }

  function press(key) {
    if (busy || done) return
    if (key === 'back') return setPin((x) => x.slice(0, -1))
    if (key === 'clear') return setPin('')
    if (pin.length >= PIN_LENGTH) return
    const next = pin + key
    setPin(next)
    if (next.length === PIN_LENGTH) submit(next)
  }

  async function reject() {
    setBusy(true)
    try {
      await onReject()
    } finally {
      setBusy(false)
    }
  }

  const preview =
    action.kind === 'send_reminder' ? p.body : action.kind === 'send_winback' ? p.messages?.[0]?.body : null

  return (
    <div className="absolute inset-0 z-40 flex items-end bg-navy/40" role="dialog" aria-modal="true" aria-label="Approve action">
      <div className="max-h-[92%] w-full overflow-y-auto rounded-t-3xl bg-white p-5 shadow-2xl">
        <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-slate-200" />
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">{KIND_LABELS[action.kind] || action.kind}</p>
            <p className="mt-1 text-[15px] font-medium leading-snug text-navy">{action.readback_text}</p>
          </div>
          <button onClick={onClose} className="rounded-full p-1 text-slate-400 hover:bg-slate-100" aria-label="Close">
            ✕
          </button>
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-3 rounded-2xl bg-slate-50 p-3 text-sm">
          {action.amount != null && action.kind !== 'send_winback' && (
            <div>
              <dt className="text-slate-500">Amount</dt>
              <dd className="text-xl font-semibold text-navy" data-testid="sheet-amount">{rupees(action.amount)}</dd>
            </div>
          )}
          <div>
            <dt className="text-slate-500">{action.kind === 'send_winback' ? 'Recipients' : 'Recipient'}</dt>
            <dd className="font-semibold text-navy">{action.recipient || '—'}</dd>
          </div>
          {action.kind === 'reschedule_payable' && (
            <div className="col-span-2 text-slate-700">
              {shortDate(p.old_due_date)} → <b className="text-navy">{shortDate(p.new_due_date)}</b>
              {p.clears_shortfall && <span className="ml-2 rounded-full bg-emerald-50 px-2 py-0.5 text-xs text-emerald-800">✓ kami door</span>}
            </div>
          )}
          {p.upi_vpa && <div className="col-span-2 text-xs text-slate-500">UPI: {p.upi_vpa}</div>}
          {p.note && <div className="col-span-2 text-xs text-slate-500">{p.note}</div>}
        </dl>

        {preview && <MessagePreview body={preview} to={action.kind === 'send_winback' ? `${p.count} grahak` : p.to} />}

        {done ? (
          <div className="mt-5 rounded-2xl bg-emerald-50 p-4 text-center text-emerald-900" role="status">
            <p className="text-lg">✓</p>
            <p className="font-medium">{done}</p>
            <button onClick={onClose} className="mt-3 rounded-full bg-navy px-6 py-2 text-sm font-semibold text-white">
              Theek hai
            </button>
          </div>
        ) : (
          <>
            <p className="mt-5 text-center text-sm font-medium text-navy">Approve karne ke liye demo PIN daalein</p>
            <div className="mt-2 flex justify-center gap-3" aria-label={`PIN entered: ${pin.length} of ${PIN_LENGTH}`}>
              {Array.from({ length: PIN_LENGTH }, (_, i) => (
                <span key={i} className={`h-3.5 w-3.5 rounded-full ${i < pin.length ? 'bg-navy' : 'border-2 border-slate-300'}`} />
              ))}
            </div>
            {error && (
              <p className="mt-2 text-center text-sm text-red-700" role="alert">
                {error}
              </p>
            )}
            <div className="mt-3 grid grid-cols-3 gap-2">
              {KEYS.map((k) => (
                <button
                  key={k}
                  type="button"
                  disabled={busy}
                  onClick={() => press(k)}
                  aria-label={k === 'back' ? 'Backspace' : k === 'clear' ? 'Clear' : k}
                  className="h-12 rounded-2xl bg-slate-100 text-lg font-semibold text-navy active:bg-sky/20 disabled:opacity-50"
                >
                  {k === 'back' ? '⌫' : k === 'clear' ? 'C' : k}
                </button>
              ))}
            </div>
            <div className="mt-3 flex items-center justify-between">
              <button onClick={reject} disabled={busy} className="rounded-full px-4 py-2 text-sm font-semibold text-red-700 hover:bg-red-50">
                Mana karein
              </button>
              <p className="text-right text-[11px] leading-tight text-slate-500">
                Demo PIN: 1234 (mock)
                <br />
                Asli UPI PIN kabhi na daalein
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// Wires the sheet to the app-wide approval queue.
export function ApprovalHost({ useAppHook }) {
  const { api, approvalQueue, closeApproval, refresh, say } = useAppHook()
  const action = approvalQueue[0]
  if (!action) return null
  return (
    <ApprovalSheet
      action={action}
      onApprove={async (pin) => {
        const r = await api.approve(action.id, pin)
        await playPaytmTune()
        refresh()
        if (r.soundbox_text) say({ text: r.soundbox_text, audio: r.audio, eventId: r.soundbox_event_id })
        return r
      }}
      onReject={async () => {
        await api.reject(action.id)
        refresh()
        closeApproval(action.id)
      }}
      onClose={() => closeApproval(action.id)}
    />
  )
}

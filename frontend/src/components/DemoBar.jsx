import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useApp, useLoad } from '../context/AppContext'
import { playPaytmTune } from '../lib/audio'

export const DEMO_MODE = typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('demo') === '1'

const SUNITA = { name: 'Sunita', amount: 650 }

// Presenter controls (?demo=1). Every button calls a /demo endpoint; nothing here touches real money.
export default function DemoBar() {
  const { api, say, refresh, requestApproval, resetSession } = useApp()
  const navigate = useNavigate()
  const { data: state } = useLoad(() => api.demoState())
  const [busy, setBusy] = useState(null)
  const [note, setNote] = useState(null)

  async function run(key, fn) {
    setBusy(key)
    setNote(null)
    try {
      setNote(await fn())
    } catch (e) {
      setNote(`⚠ ${e.message}`)
    } finally {
      setBusy(null)
    }
  }

  const reset = () =>
    run('reset', async () => {
      const r = await api.reset()
      resetSession()
      navigate('/')
      return `Reset · demo date ${r.demo_date}`
    })

  const jump = () =>
    run('jump', async () => {
      const r = await api.jumpToFriday()
      requestApproval(await api.actions('pending'))
      refresh()
      navigate('/udhaar')
      const sent = r.tick.reminders.filter((x) => x.auto_sent).length
      const drafted = r.tick.reminders.length - sent
      return `Friday 10:00 · ${sent} reminder preview${sent === 1 ? '' : 's'}${drafted ? `, ${drafted} awaiting approval` : ''}`
    })

  const pay = () =>
    run('pay', async () => {
      await playPaytmTune()
      const r = await api.simulatePayment(SUNITA.amount, SUNITA.name)
      say({ text: r.soundbox_text, eventId: r.soundbox_event_id })
      refresh()
      navigate('/udhaar')
      return r.settled_udhaar ? `${r.settled_udhaar.customer}: udhaar closed` : 'Payment received (no open udhaar matched)'
    })

  const briefing = () =>
    run('briefing', async () => {
      const b = await api.briefing()
      navigate('/')
      say({ text: b.spoken_text })
      return 'Playing Subah ki Report'
    })

  const buttons = [
    ['reset', '↺ Reset', reset],
    ['briefing', '▶ Briefing', briefing],
    ['jump', '⏩ Jump to Friday', jump],
    ['pay', `₹ Sunita pays ${SUNITA.amount}`, pay],
  ]

  return (
    <div className="w-full max-w-[390px] rounded-2xl bg-slate-900 p-2.5 text-white shadow lg:max-w-none" role="toolbar" aria-label="Demo controls">
      <div className="flex items-center justify-between px-1 text-[11px] text-slate-400">
        <span className="font-semibold uppercase tracking-wide">Demo controls</span>
        {state && (
          <span>
            Day {state.day} · {state.pending_actions} pending · {state.open_udhaar} udhaar open
          </span>
        )}
      </div>
      <div className="mt-2 grid grid-cols-2 gap-1.5">
        {buttons.map(([key, label, fn]) => (
          <button
            key={key}
            onClick={fn}
            disabled={busy !== null}
            className="rounded-xl bg-white/10 px-2 py-2 text-[12px] font-semibold hover:bg-white/20 disabled:opacity-50"
          >
            {busy === key ? '…' : label}
          </button>
        ))}
      </div>
      {note && <p className="mt-2 px-1 text-[11px] text-sky-200" role="status">{note}</p>}
    </div>
  )
}

import { useApp, useLoad } from '../context/AppContext'
import Card, { Loading, ErrorNote } from '../components/Card'

function Toggle({ label, description, value, onChange, disabled }) {
  return (
    <div className="flex items-start justify-between gap-3 py-3 border-b border-slate-100 last:border-0">
      <div className="min-w-0">
        <p className={`text-[13px] font-medium ${disabled ? 'text-slate-400' : 'text-navy'}`}>{label}</p>
        {description && <p className="text-[11px] text-slate-400 mt-0.5">{description}</p>}
      </div>
      {disabled ? (
        <span className="shrink-0 rounded-full bg-slate-100 px-3 py-1 text-[11px] font-medium text-slate-500 ring-1 ring-slate-200">
          Always PIN
        </span>
      ) : (
        <button
          onClick={() => onChange(value === 'auto' ? 'suggest' : 'auto')}
          aria-label={`Toggle ${label}`}
          className={`shrink-0 relative inline-flex h-7 w-13 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-sky ${
            value === 'auto' ? 'bg-sky' : 'bg-slate-200'
          }`}
        >
          <span
            className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
              value === 'auto' ? 'translate-x-7' : 'translate-x-1'
            }`}
          />
        </button>
      )}
    </div>
  )
}

export default function Settings() {
  const { api, reloadStatus, status } = useApp()
  const { data: settings, loading, error, reload } = useLoad(() => api.settings())
  const { data: merchant } = useLoad(() => api.merchant())

  async function update(patch) {
    try {
      await api.updateSettings(patch)
      reload()
      reloadStatus()
    } catch {}
  }

  return (
    <div className="space-y-4 p-4 pb-6">
      <h1 className="text-[17px] font-semibold text-navy">Settings</h1>

      {loading && !settings && <Loading />}
      <ErrorNote error={error} />

      {/* Merchant info */}
      {merchant && (
        <Card title="Dukaan">
          <dl className="space-y-1.5 text-[13px]">
            <div className="flex justify-between">
              <dt className="text-slate-500">Naam</dt>
              <dd className="font-medium text-navy">{merchant.owner_name || merchant.name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Dukaan</dt>
              <dd className="font-medium text-navy">{merchant.name}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Bhasha</dt>
              <dd className="font-medium text-navy capitalize">{merchant.language || 'hi'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">UPI</dt>
              <dd className="font-medium text-navy">{merchant.upi_vpa || '—'}</dd>
            </div>
          </dl>
        </Card>
      )}

      {/* Autonomy toggles */}
      {settings && (
        <Card title="Auto-approve Settings">
          <p className="text-[11px] text-slate-500 mb-2">
            "Auto" = agent khud karta hai. "Suggest" = aapka approve chahiye.
          </p>
          <Toggle
            label="Udhaar reminders"
            description="Auto-send reminders when due"
            value={settings.autonomy_udhaar || 'suggest'}
            onChange={(v) => update({ autonomy_udhaar: v })}
          />
          <Toggle
            label="Growth win-back"
            description="Auto-send win-back offers"
            value={settings.autonomy_growth || 'suggest'}
            onChange={(v) => update({ autonomy_growth: v })}
          />
          <Toggle
            label="Supplier payments"
            description="Paisa hilta hai (demo) — hamesha PIN"
            disabled
          />
          <Toggle
            label="Cash Radar rescheduling"
            description="Paisa hilta hai (demo) — hamesha PIN"
            disabled
          />
        </Card>
      )}

      {/* About */}
      <Card title="About Vyapar Hub">
        <div className="space-y-1.5 text-[12px] text-slate-500">
          <p>🏷 Version: Demo · Hackathon build</p>
          <p>⚠ All data is synthetic (seeded). No real transactions.</p>
          <p>🔒 Demo PIN: 1234. No real UPI PIN is ever asked.</p>
          <p>🤖 AI: {status ? `${status.llm}${status.llm_model ? ` (${status.llm_model})` : ''}` : '…'}</p>
        </div>
      </Card>
    </div>
  )
}

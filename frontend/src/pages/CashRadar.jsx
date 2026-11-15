import { useApp, useLoad } from '../context/AppContext'
import Card, { Loading, ErrorNote, Button } from '../components/Card'
import RadarChart from '../components/RadarChart'
import AssistantPanel from '../components/AssistantPanel'
import { rupees, shortDate } from '../lib/format'

const CASH_PHRASES = [
  'Agarwal ka payment 7 tareekh ko kar do',
  'Cash ki kya situation hai?',
  'Safe date kab hai?',
]

function StatTile({ label, value, sub, alert }) {
  return (
    <div className={`rounded-2xl p-3 flex-1 min-w-0 ${alert ? 'bg-red-50' : 'bg-slate-50'}`}>
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className={`text-[18px] font-semibold mt-0.5 ${alert ? 'text-[#d03b3b]' : 'text-navy'}`}>{value}</p>
      {sub && <p className="text-[11px] text-slate-500 mt-0.5">{sub}</p>}
    </div>
  )
}

export default function CashRadar() {
  const { api, requestApproval } = useApp()
  const { data: radar, loading, error } = useLoad(() => api.radar())
  const { data: merchant } = useLoad(() => api.merchant())

  const shortfalls = radar?.shortfalls || []
  const buffer = merchant?.cash_buffer ?? 0

  async function handleReschedule(sf) {
    try {
      // Find the first upcoming payable via assistant or use the fix text as a suggestion
      // For the demo, trigger the full agent flow with the fix suggestion
      requestApproval([])
    } catch {}
  }

  return (
    <div className="space-y-4 p-4 pb-6">
      <h1 className="text-[17px] font-semibold text-navy">Cash Radar</h1>

      {loading && !radar && <Loading />}
      <ErrorNote error={error} />

      {radar && (
        <>
          {/* Balance stat tiles */}
          <div className="flex gap-3">
            <StatTile
              label="Buffer"
              value={rupees(buffer)}
              sub="minimum required"
            />
            {shortfalls.length > 0 ? (
              <StatTile
                label="Next shortfall"
                value={shortDate(shortfalls[0].date)}
                sub={rupees(shortfalls[0].amount) + ' kami'}
                alert
              />
            ) : (
              <StatTile
                label="Forecast"
                value="Safe"
                sub={radar.summary_text ? radar.summary_text.slice(0, 30) : '14 din ke liye'}
              />
            )}
          </div>

          {/* Shortfall card */}
          {shortfalls.length > 0 && (
            <div className="rounded-2xl bg-red-50 p-4 ring-1 ring-red-100">
              <div className="flex items-start gap-2">
                <span className="text-[#d03b3b] text-lg">⚠</span>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-semibold text-[#d03b3b]">Cash shortfall detected</p>
                  {shortfalls.map((sf, i) => (
                    <div key={i} className="mt-2">
                      <p className="text-[12px] text-red-800">
                        <b>{shortDate(sf.date)}:</b> {sf.cause}
                      </p>
                      {sf.fix && (
                        <p className="text-[12px] text-emerald-800 mt-0.5">
                          💡 Fix: {sf.fix}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              <p className="mt-3 text-[11px] text-slate-600">
                Neeche assistant se payment reschedule karein.
              </p>
            </div>
          )}

          {/* Chart */}
          <Card title="14-day Forecast">
            {radar.days && radar.days.length > 0 ? (
              <RadarChart
                data={radar.days}
                flaggedDays={radar.flagged_days || []}
                buffer={buffer}
              />
            ) : (
              <p className="py-4 text-center text-sm text-slate-400">Chart data nahi mili.</p>
            )}
          </Card>

          {/* Summary */}
          {radar.summary_text && (
            <p className="rounded-xl bg-slate-50 px-3 py-2.5 text-[13px] text-slate-700">
              {radar.summary_text}
            </p>
          )}
        </>
      )}

      <AssistantPanel
        suggestions={CASH_PHRASES}
        title="Cash ke baare mein poochhiye"
      />
    </div>
  )
}

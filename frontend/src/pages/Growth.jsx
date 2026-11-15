import { useState } from 'react'
import { useApp, useLoad } from '../context/AppContext'
import Card, { Loading, ErrorNote, Button } from '../components/Card'
import Heatmap from '../components/Heatmap'
import AssistantPanel from '../components/AssistantPanel'
import { rupees, shortDate } from '../lib/format'

const GROWTH_PHRASES = [
  "14 regulars haven't come in 3 weeks",
  'Win-back offer bhejo',
  'Peak hours kab hain?',
]

function StatTile({ label, value, sub, positive }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-3 flex-1 min-w-0">
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className={`text-[16px] font-semibold mt-0.5 ${positive === true ? 'text-emerald-700' : positive === false ? 'text-[#d03b3b]' : 'text-navy'}`}>
        {value}
      </p>
      {sub && <p className="text-[11px] text-slate-400 mt-0.5">{sub}</p>}
    </div>
  )
}

export default function Growth() {
  const { api, requestApproval } = useApp()
  const { data: insights, loading, error } = useLoad(() => api.growth())
  const [winbackBusy, setWinbackBusy] = useState(false)
  const [winbackErr, setWinbackErr] = useState(null)

  const lapsed = insights?.lapsed || []
  const slowDays = insights?.slow_days || []
  const festivals = insights?.festival_comparison || []
  const rawHeatmap = insights?.peak_heatmap
  const heatmapData = Array.isArray(rawHeatmap) ? rawHeatmap : (rawHeatmap?.data || [])

  async function handleWinback() {
    setWinbackBusy(true)
    setWinbackErr(null)
    try {
      const r = await api.draftWinback(10)
      requestApproval(r.pending_actions || [])
    } catch (e) {
      setWinbackErr(e.message)
    } finally {
      setWinbackBusy(false)
    }
  }

  return (
    <div className="space-y-4 p-4 pb-6">
      <h1 className="text-[17px] font-semibold text-navy">Growth</h1>

      {loading && !insights && <Loading />}
      <ErrorNote error={error} />

      {insights && (
        <>
          {/* Lapsed customers */}
          {lapsed.length > 0 && (
            <Card
              title={`${lapsed.length} regular nahi aaye (3 hafte se)`}
              action={
                <Button
                  variant="sky"
                  className="text-[11px]"
                  onClick={handleWinback}
                  disabled={winbackBusy}
                >
                  🎁 Win-back offer
                </Button>
              }
            >
              {winbackErr && <p className="mb-2 text-[11px] text-red-700">{winbackErr}</p>}
              <div className="space-y-2 mt-1">
                {lapsed.slice(0, 8).map((c) => (
                  <div key={c.customer_id || c.name} className="flex items-center justify-between text-[13px]">
                    <span className="text-navy font-medium">{c.name}</span>
                    <span className="text-slate-500 text-[12px]">
                      {c.days_since} din pehle aaye the
                      {c.last_visit && <span className="ml-1">({shortDate(c.last_visit)})</span>}
                    </span>
                  </div>
                ))}
                {lapsed.length > 8 && (
                  <p className="text-[11px] text-slate-400">+{lapsed.length - 8} aur...</p>
                )}
              </div>
            </Card>
          )}

          {/* Peak heatmap */}
          <Card title="Peak Hours Heatmap">
            {heatmapData.length > 0 ? (
              <Heatmap data={heatmapData} />
            ) : (
              <p className="py-4 text-center text-sm text-slate-400">Heatmap data nahi mili.</p>
            )}
          </Card>

          {/* Slow days */}
          {slowDays.length > 0 && (
            <Card title="Slow Days">
              <div className="flex flex-wrap gap-2 mt-1">
                {slowDays.map((d) => (
                  <StatTile
                    key={d.day}
                    label={d.day}
                    value={rupees(d.avg_sales)}
                    sub={d.vs_usual_pct != null ? `${d.vs_usual_pct > 0 ? '+' : ''}${d.vs_usual_pct}% vs usual` : null}
                    positive={d.vs_usual_pct != null ? d.vs_usual_pct >= 0 : undefined}
                  />
                ))}
              </div>
            </Card>
          )}

          {/* Festival comparison */}
          {festivals.length > 0 && (
            <Card title="Festival Performance">
              <div className="space-y-3 mt-1">
                {festivals.map((f, i) => (
                  <div key={i} className="rounded-xl bg-slate-50 p-3">
                    <p className="text-[13px] font-semibold text-navy mb-2">{f.festival} {f.year || ''}</p>
                    <div className="flex gap-3">
                      <StatTile
                        label="Avg sales"
                        value={rupees(f.avg_sales || f.after_avg)}
                        positive={f.pct_change >= 0}
                      />
                      <StatTile
                        label="Baseline"
                        value={rupees(f.baseline_avg || f.before_avg)}
                      />
                      {f.pct_change != null && (
                        <StatTile
                          label="Change"
                          value={`${f.pct_change > 0 ? '+' : ''}${f.pct_change}%`}
                          positive={f.pct_change >= 0}
                        />
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}

      <AssistantPanel suggestions={GROWTH_PHRASES} title="Growth ke baare mein poochhiye" />
    </div>
  )
}

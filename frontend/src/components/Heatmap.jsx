import { useState } from 'react'
import { rupees, rupeesShort } from '../lib/format'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function hourLabel(h) {
  if (h === 12) return '12p'
  return h < 12 ? `${h}a` : `${h - 12}p`
}

// Single-hue sequential heatmap of average sales per weekday × hour (peak_hours.cells from the API).
export default function Heatmap({ cells = [], hours = [] }) {
  const [numbers, setNumbers] = useState(false)
  if (!cells.length || !hours.length) return <p className="py-6 text-center text-sm text-slate-400">Peak data nahi mili.</p>

  const lookup = new Map(cells.map((c) => [`${c.weekday}-${c.hour}`, c]))
  const max = Math.max(1, ...cells.map((c) => c.avg_sales))
  const tint = (v) => `rgba(0,185,241,${(0.06 + 0.94 * (v / max)).toFixed(3)})`

  return (
    <div>
      <div className="grid gap-px" style={{ gridTemplateColumns: `2rem repeat(${hours.length}, minmax(0, 1fr))` }} role="table" aria-label="Average sales by weekday and hour">
        <span />
        {hours.map((h) => (
          <span key={h} className="text-center text-[9px] text-slate-500" role="columnheader">
            {h % 3 === 0 ? hourLabel(h) : ''}
          </span>
        ))}
        {DAYS.map((d, wd) => (
          <div key={d} className="contents" role="row">
            <span className="pr-1 text-right text-[10px] leading-6 text-slate-500" role="rowheader">{d}</span>
            {hours.map((h) => {
              const c = lookup.get(`${wd}-${h}`)
              const v = c?.avg_sales || 0
              return (
                <span
                  key={h}
                  role="cell"
                  title={`${d} ${hourLabel(h)}: ${rupees(v)} avg`}
                  className={`flex h-6 items-center justify-center rounded-[2px] text-[8px] ${v / max > 0.6 ? 'text-white' : 'text-navy'}`}
                  style={{ backgroundColor: tint(v) }}
                >
                  {numbers && v ? rupeesShort(v).replace('₹', '') : ''}
                </span>
              )
            })}
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-2 pl-8">
        <span className="text-[10px] text-slate-500">{rupees(0)}</span>
        <div className="h-2 flex-1 rounded-full" style={{ background: `linear-gradient(to right, ${tint(0)}, ${tint(max)})` }} aria-hidden />
        <span className="text-[10px] text-slate-500">{rupees(max)} / ghanta</span>
      </div>
      <button onClick={() => setNumbers((n) => !n)} className="mt-1 text-[11px] font-semibold text-sky-700" aria-pressed={numbers}>
        {numbers ? 'Numbers chhupao' : 'Numbers dikhao'}
      </button>
    </div>
  )
}

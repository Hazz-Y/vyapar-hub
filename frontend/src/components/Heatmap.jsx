const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const HOUR_TICKS = [0, 6, 12, 18]

function formatHour(h) {
  if (h === 0) return '12am'
  if (h === 12) return '12pm'
  return h < 12 ? `${h}am` : `${h - 12}pm`
}

function formatDay(d) {
  return ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][d] || d
}

export default function Heatmap({ data = [] }) {
  if (!data.length) {
    return <p className="py-6 text-center text-sm text-slate-400">Peak data nahi mili.</p>
  }

  // Build a lookup map: {day-hour: count}
  const lookup = {}
  let maxCount = 1
  for (const item of data) {
    const key = `${item.day}-${item.hour}`
    lookup[key] = (lookup[key] || 0) + item.count
    if (lookup[key] > maxCount) maxCount = lookup[key]
  }

  return (
    <div>
      {/* Column headers */}
      <div className="flex pl-8">
        {DAYS.map((d) => (
          <div key={d} className="flex-1 text-center text-[10px] font-medium text-slate-500 pb-1">
            {d[0]}
          </div>
        ))}
      </div>

      {/* Grid */}
      <div className="relative">
        {Array.from({ length: 24 }, (_, hour) => {
          const showTick = HOUR_TICKS.includes(hour)
          return (
            <div key={hour} className="flex items-center">
              <div className="w-8 shrink-0 text-right pr-1.5 text-[10px] text-slate-400 leading-none">
                {showTick ? formatHour(hour) : ''}
              </div>
              {Array.from({ length: 7 }, (_, day) => {
                const count = lookup[`${day}-${hour}`] || 0
                const opacity = count === 0 ? 0.06 : 0.08 + 0.87 * (count / maxCount)
                return (
                  <div
                    key={day}
                    className="flex-1 h-5 cursor-default"
                    style={{ backgroundColor: `rgba(0,185,241,${opacity.toFixed(3)})` }}
                    title={`${formatDay(day)} ${formatHour(hour)} — ${count} transactions`}
                  />
                )
              })}
            </div>
          )
        })}
      </div>

      {/* Scale legend */}
      <div className="mt-3 flex items-center gap-2 pl-8">
        <span className="text-[10px] text-slate-400">Low</span>
        <div
          className="flex-1 h-2.5 rounded-full"
          style={{ background: 'linear-gradient(to right, rgba(0,185,241,0.08), rgba(0,185,241,1))' }}
          aria-label="Color scale: low to high transaction count"
        />
        <span className="text-[10px] text-slate-400">High ({maxCount})</span>
      </div>
    </div>
  )
}

import { useState } from 'react'
import {
  Area, CartesianGrid, ComposedChart, Legend, Line, ReferenceArea, ReferenceLine,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { rupees, rupeesShort, shortDate } from '../lib/format'

const SKY = '#00B9F1'
const NAVY = '#002E6E'
const CRITICAL = '#d03b3b'

function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="rounded-xl bg-white p-2.5 text-[12px] shadow-lg ring-1 ring-slate-200">
      <p className="font-semibold text-navy">
        {shortDate(d.date)} · {d.weekday}
      </p>
      <p className="text-slate-600">Likely: <b className="text-navy">{rupees(d.balance_p50)}</b></p>
      <p className="text-slate-500">Range: {rupees(d.balance_p10)} – {rupees(d.balance_p90)}</p>
      {d.payables?.map((p) => (
        <p key={p.id} className="text-slate-500">Bill: {p.supplier} {rupees(p.amount)}</p>
      ))}
      {d.below_buffer && <p className="font-semibold text-[#d03b3b]">⚠ Buffer se neeche</p>}
    </div>
  )
}

// End-of-day balance forecast: p10–p90 range, p50 line, buffer line, shortfall days shaded.
export default function RadarChart({ days = [], shortfalls = [], buffer = 0, height = 230 }) {
  const [table, setTable] = useState(false)
  const data = days.map((d) => ({ ...d, range: [d.balance_p10, d.balance_p90] }))

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#e2e8f0" strokeWidth={0.5} vertical={false} />
          <XAxis dataKey="date" tickFormatter={shortDate} tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={{ stroke: '#cbd5e1' }} interval="preserveStartEnd" minTickGap={18} />
          <YAxis tickFormatter={rupeesShort} tick={{ fontSize: 10, fill: '#64748b' }} tickLine={false} axisLine={false} width={48} />
          <Tooltip content={<ChartTooltip />} cursor={{ stroke: '#94a3b8', strokeWidth: 1 }} />
          <Legend verticalAlign="top" height={24} iconSize={10} wrapperStyle={{ fontSize: 11, color: '#475569' }} />
          {shortfalls.map((s) =>
            s.date === s.last_day ? (
              <ReferenceLine key={s.date} x={s.date} stroke={CRITICAL} strokeOpacity={0.35} strokeWidth={10} />
            ) : (
              <ReferenceArea key={s.date} x1={s.date} x2={s.last_day} fill={CRITICAL} fillOpacity={0.08} />
            ),
          )}
          <Area dataKey="range" name="Range (p10–p90)" fill={SKY} fillOpacity={0.18} stroke="none" isAnimationActive={false} activeDot={false} />
          <Line dataKey="balance_p50" name="Likely balance" stroke={NAVY} strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
          <ReferenceLine
            y={buffer}
            stroke={CRITICAL}
            strokeDasharray="4 3"
            strokeWidth={1.5}
            label={{ value: `Buffer ${rupees(buffer)}`, fill: CRITICAL, fontSize: 10, position: 'insideBottomLeft' }}
          />
        </ComposedChart>
      </ResponsiveContainer>

      <button onClick={() => setTable((t) => !t)} className="mt-1 text-[11px] font-semibold text-sky-700" aria-expanded={table}>
        {table ? 'Chart only' : 'Table view'}
      </button>
      {table && (
        <div className="mt-2 max-h-64 overflow-auto rounded-xl ring-1 ring-slate-200">
          <table className="w-full text-[12px]">
            <thead className="sticky top-0 bg-slate-50 text-left text-slate-500">
              <tr>
                <th className="px-2 py-1.5 font-medium">Din</th>
                <th className="px-2 py-1.5 text-right font-medium">Kam se kam</th>
                <th className="px-2 py-1.5 text-right font-medium">Likely</th>
                <th className="px-2 py-1.5 text-right font-medium">Bills</th>
              </tr>
            </thead>
            <tbody>
              {days.map((d) => (
                <tr key={d.date} className={`border-t border-slate-100 ${d.below_buffer ? 'bg-red-50' : ''}`}>
                  <td className="px-2 py-1.5 text-slate-700">
                    {shortDate(d.date)} {d.weekday}
                    {d.below_buffer && <span className="ml-1 text-[#d03b3b]" aria-label="below buffer">⚠</span>}
                  </td>
                  <td className="px-2 py-1.5 text-right text-slate-600">{rupees(d.balance_p10)}</td>
                  <td className="px-2 py-1.5 text-right font-medium text-navy">{rupees(d.balance_p50)}</td>
                  <td className="px-2 py-1.5 text-right text-slate-600">{d.payables_total ? rupees(d.payables_total) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

import { useState } from 'react'
import {
  ComposedChart, Area, Line, ReferenceLine, ReferenceArea,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import { rupees, rupeesShort, shortDate } from '../lib/format'

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null
  const d = payload[0]?.payload || {}
  return (
    <div className="rounded-xl bg-white p-3 shadow-lg ring-1 ring-slate-200 text-[12px]">
      <p className="font-semibold text-navy mb-1">{label ? shortDate(label) : ''}</p>
      <p className="text-slate-500">P10: <span className="text-navy font-medium">{rupees(d.p10)}</span></p>
      <p className="text-slate-500">P50: <span className="text-[#00B9F1] font-medium">{rupees(d.p50)}</span></p>
      <p className="text-slate-500">P90: <span className="text-navy font-medium">{rupees(d.p90)}</span></p>
      {d.balance != null && (
        <p className="text-slate-500 mt-1">Balance: <span className="font-medium">{rupees(d.balance)}</span></p>
      )}
    </div>
  )
}

export default function RadarChart({ data = [], flaggedDays = [], buffer = 0 }) {
  const [tableOpen, setTableOpen] = useState(false)
  const flagSet = new Set(flaggedDays.map((d) => d.date))
  const chartData = data.map((d) => ({
    ...d,
    band: Math.max(0, d.p90 - d.p10),
  }))

  return (
    <div>
      <ResponsiveContainer width="100%" height={240}>
        <ComposedChart data={chartData} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#f1f5f9" strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={(v) => shortDate(v)}
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tickFormatter={(v) => rupeesShort(v)}
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            tickLine={false}
            axisLine={false}
            width={56}
          />
          <Tooltip content={<ChartTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: 11, paddingTop: 4 }}
            formatter={(value) => <span className="text-slate-600">{value}</span>}
          />

          {/* P10–P90 band: stacked areas */}
          <Area
            stackId="cf"
            dataKey="p10"
            fill="transparent"
            stroke="none"
            name="P10 (base)"
            legendType="none"
          />
          <Area
            stackId="cf"
            dataKey="band"
            fill="rgba(0,185,241,0.15)"
            stroke="none"
            name="P10–P90 band"
          />

          <Line
            dataKey="p50"
            stroke="#00B9F1"
            strokeWidth={2}
            dot={false}
            name="Forecast (p50)"
            activeDot={{ r: 4, strokeWidth: 0 }}
          />

          {buffer > 0 && (
            <ReferenceLine
              y={buffer}
              stroke="#d03b3b"
              strokeDasharray="4 2"
              strokeWidth={1.5}
              label={{ value: 'Buffer', fill: '#d03b3b', fontSize: 10, position: 'insideTopLeft' }}
            />
          )}

          {flaggedDays.map((fd) => (
            <ReferenceArea
              key={fd.date}
              x1={fd.date}
              x2={fd.date}
              fill="rgba(208,59,59,0.1)"
              ifOverflow="visible"
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>

      <button
        onClick={() => setTableOpen((o) => !o)}
        className="mt-2 text-[11px] font-semibold text-sky-700 hover:underline"
      >
        {tableOpen ? 'Hide table' : 'Table view'}
      </button>

      {tableOpen && (
        <div className="mt-2 overflow-x-auto rounded-xl bg-slate-50 ring-1 ring-slate-200">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="px-3 py-2 font-medium">Date</th>
                <th className="px-3 py-2 font-medium text-right">P10</th>
                <th className="px-3 py-2 font-medium text-right">P50</th>
                <th className="px-3 py-2 font-medium text-right">P90</th>
              </tr>
            </thead>
            <tbody>
              {data.map((d) => (
                <tr
                  key={d.date}
                  className={`border-b border-slate-100 last:border-0 ${flagSet.has(d.date) ? 'bg-red-50' : ''}`}
                >
                  <td className="px-3 py-1.5 text-slate-700">
                    {shortDate(d.date)}
                    {flagSet.has(d.date) && <span className="ml-1 text-[#d03b3b]">⚠</span>}
                  </td>
                  <td className="px-3 py-1.5 text-right text-slate-600">{rupees(d.p10)}</td>
                  <td className="px-3 py-1.5 text-right font-medium text-navy">{rupees(d.p50)}</td>
                  <td className="px-3 py-1.5 text-right text-slate-600">{rupees(d.p90)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

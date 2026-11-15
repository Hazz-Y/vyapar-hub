// Display formatting only. No business arithmetic happens in the UI: values arrive computed.

const INR = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })

export function rupees(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  const n = Math.round(Number(value))
  return `${n < 0 ? '-' : ''}₹${INR.format(Math.abs(n))}`
}

// Compact axis ticks: 12000 -> "₹12k", 150000 -> "₹1.5L"
export function rupeesShort(value) {
  const n = Number(value)
  const abs = Math.abs(n)
  const sign = n < 0 ? '-' : ''
  if (abs >= 100000) return `${sign}₹${trim(abs / 100000)}L`
  if (abs >= 1000) return `${sign}₹${trim(abs / 1000)}k`
  return `${sign}₹${abs}`
}

function trim(x) {
  return x.toFixed(1).replace(/\.0$/, '')
}

export function shortDate(iso) {
  const d = new Date(`${iso}T00:00:00`)
  return `${d.getDate()} ${d.toLocaleString('en-IN', { month: 'short' })}`
}

export function weekday(iso) {
  return new Date(`${iso}T00:00:00`).toLocaleString('en-IN', { weekday: 'short' })
}

export const KIND_LABELS = {
  pay_supplier: 'Supplier payment',
  reschedule_payable: 'Payment reschedule',
  log_udhaar: 'Udhaar entry',
  send_reminder: 'Udhaar reminder',
  send_winback: 'Win-back offer',
}

export const STATUS_CHIP = {
  open: { label: 'Khula', cls: 'bg-amber-50 text-amber-800 ring-amber-200' },
  reminded: { label: 'Reminder gaya', cls: 'bg-sky-50 text-sky-800 ring-sky-200' },
  settled: { label: 'Chuka diya', cls: 'bg-emerald-50 text-emerald-800 ring-emerald-200' },
  overdue: { label: 'Overdue', cls: 'bg-red-50 text-red-800 ring-red-200' },
}

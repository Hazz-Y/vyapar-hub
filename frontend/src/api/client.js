// Thin API client. Every number shown in the UI comes from these endpoints (tool / service output).
export const API_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : detail?.reason || detail?.error || JSON.stringify(detail))
    this.status = status
    this.detail = detail
  }
}

function withQuery(path, params) {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params || {})) {
    if (v !== undefined && v !== null && v !== '') q.set(k, String(v))
  }
  const s = q.toString()
  return s ? `${path}${path.includes('?') ? '&' : '?'}${s}` : path
}

export async function request(path, { method = 'GET', body, params, form } = {}) {
  const init = { method, headers: {} }
  if (form) {
    init.body = form // multipart: let the browser set the boundary
  } else if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(body)
  }
  const res = await fetch(`${API_URL}${withQuery(path, params)}`, init)
  const type = res.headers.get('content-type') || ''
  const data = type.includes('application/json') ? await res.json() : await res.text()
  if (!res.ok) throw new ApiError(res.status, data && typeof data === 'object' && 'detail' in data ? data.detail : data)
  return data
}

export function createApi(merchantId = 1) {
  const m = { merchant_id: merchantId }
  return {
    health: () => request('/health'),
    status: () => request('/status'),
    merchant: () => request(`/merchants/${merchantId}`),
    salesSummary: () => request('/sales/summary', { params: m }),
    briefing: () => request('/briefing/today', { params: m }),
    radar: (whatIf) => request('/cash/radar', { params: { ...m, ...whatIf } }),
    backtest: () => request('/cash/backtest', { params: m }),
    payables: (status = 'upcoming') => request('/payables', { params: { ...m, status } }),
    draftPay: (payableId) => request(`/payables/${payableId}/pay/draft`, { method: 'POST', params: m }),
    draftReschedule: (payableId, newDate) =>
      request(`/payables/${payableId}/reschedule/draft`, { method: 'POST', params: m, body: { new_date: newDate || null } }),
    matching: () => request('/suppliers/matching', { params: { ...m, limit: 500 } }),
    gstExportUrl: (month) => `${API_URL}${withQuery('/suppliers/gst-export.csv', { ...m, month })}`,
    udhaar: (status) => request('/udhaar', { params: { ...m, status } }),
    addUdhaar: (entry) => request('/udhaar', { method: 'POST', params: m, body: entry }),
    remind: (udhaarId) => request(`/udhaar/${udhaarId}/remind`, { method: 'POST', params: m }),
    messages: () => request('/messages', { params: { ...m, limit: 30 } }),
    growth: () => request('/growth/insights', { params: m }),
    draftWinback: (discountPct = 10) => request('/growth/winback/draft', { method: 'POST', params: m, body: { discount_pct: discountPct } }),
    settings: () => request('/settings', { params: m }),
    updateSettings: (patch) => request('/settings', { method: 'PUT', params: m, body: patch }),
    actions: (status = 'pending') => request('/actions', { params: { ...m, status } }),
    approve: (id, pin) => request(`/actions/${id}/approve`, { method: 'POST', body: { pin } }),
    reject: (id) => request(`/actions/${id}/reject`, { method: 'POST' }),
    chat: (message, history = []) => request('/agent/chat', { method: 'POST', params: m, body: { message, history } }),
    voiceTurn: (blob, history = []) => {
      const form = new FormData()
      const ext = (blob.type || 'audio/webm').includes('mp4') ? 'mp4' : 'webm'
      form.append('audio', blob, `command.${ext}`)
      form.append('history', JSON.stringify(history))
      return request('/voice/turn', { method: 'POST', params: m, form })
    },
    speak: (text) => request('/voice/speak', { method: 'POST', body: { text } }),
    soundboxEvents: (afterId = 0) => request('/soundbox/events', { params: { ...m, after_id: afterId } }),
    simulatePayment: (amount, payerName) =>
      request('/demo/simulate-payment', { method: 'POST', params: m, body: { amount, payer_name: payerName } }),
    reset: () => request('/demo/reset', { method: 'POST' }),
    jumpToFriday: () => request('/demo/jump-to-friday', { method: 'POST' }),
    demoState: () => request('/demo/state', { params: m }),
    display: (status, amount, line1, line2) =>
      request('/hardware/display', { method: 'POST', body: { status, amount, line1, line2 } }),
    setSpeaker: (speaking, text = '') =>
      request('/hardware/speaker', { method: 'POST', body: { speaking, text } }),
  }
}

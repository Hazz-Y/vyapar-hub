export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export async function request(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail || detail } catch { /* not json */ }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  const type = res.headers.get('content-type') || ''
  return type.includes('application/json') ? res.json() : res.text()
}

export const api = {
  health: () => request('/health'),
}

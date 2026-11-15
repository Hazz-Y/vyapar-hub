import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createApi, ApiError } from '../api/client'

beforeEach(() => {
  global.fetch = vi.fn()
})

function mockJson(data, status = 200) {
  global.fetch.mockResolvedValueOnce({
    ok: status < 400,
    status,
    headers: { get: () => 'application/json' },
    json: async () => data,
    text: async () => JSON.stringify(data),
  })
}

describe('createApi', () => {
  const api = createApi(1)

  it('health calls /health', async () => {
    mockJson({ status: 'ok' })
    await api.health()
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('/health'), expect.any(Object))
  })

  it('radar passes merchant_id', async () => {
    mockJson({ days: [], flagged_days: [], shortfalls: [], summary_text: '' })
    await api.radar()
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining('merchant_id=1'), expect.any(Object))
  })

  it('draftPay posts to correct path', async () => {
    mockJson({ pending_actions: [] })
    await api.draftPay(42)
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/payables/42/pay/draft'),
      expect.any(Object),
    )
  })

  it('draftReschedule posts to correct path', async () => {
    mockJson({ pending_actions: [] })
    await api.draftReschedule(7, '2026-12-01')
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/payables/7/reschedule/draft'),
      expect.any(Object),
    )
  })

  it('addUdhaar sends POST body', async () => {
    mockJson({ id: 1 })
    await api.addUdhaar({ customer_name: 'Test', amount: 500, due_date: '2026-11-20', phone: null })
    const [, init] = fetch.mock.calls[0]
    expect(init.method).toBe('POST')
    const body = JSON.parse(init.body)
    expect(body.amount).toBe(500)
  })

  it('ApiError wraps non-ok response', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 404,
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'Not found' }),
      text: async () => '{"detail":"Not found"}',
    })
    await expect(api.merchant()).rejects.toThrow(ApiError)
  })

  it('ApiError has status property', async () => {
    global.fetch.mockResolvedValueOnce({
      ok: false,
      status: 422,
      headers: { get: () => 'application/json' },
      json: async () => ({ detail: 'Unprocessable' }),
      text: async () => '{"detail":"Unprocessable"}',
    })
    try {
      await api.merchant()
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError)
      expect(e.status).toBe(422)
    }
  })

  it('gstExportUrl includes month param', () => {
    const url = api.gstExportUrl('2026-11')
    expect(url).toContain('gst-export.csv')
    expect(url).toContain('2026-11')
  })
})

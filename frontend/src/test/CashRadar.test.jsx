import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import CashRadar from '../pages/CashRadar'
import { AppProvider } from '../context/AppContext'
import { MemoryRouter } from 'react-router'

const RADAR_DATA = {
  merchant_id: 1,
  as_of: '2026-11-15T08:30:00',
  balance_now: 16000,
  balance_now_text: '₹16,000',
  buffer: 5000,
  horizon_days: 14,
  days: [
    {
      date: '2026-11-15',
      weekday: 'Sun',
      inflow_p10: 13000,
      inflow_p50: 16000,
      inflow_p90: 20000,
      payables_total: 13800,
      payables: [{ id: 915, supplier: 'Sharma Milk Dairy', amount: 13800 }],
      balance_p10: 15000,
      balance_p50: 18000,
      balance_p90: 23000,
      below_buffer: false,
    },
    {
      date: '2026-11-20',
      weekday: 'Fri',
      inflow_p10: 8000,
      inflow_p50: 10000,
      inflow_p90: 12000,
      payables_total: 22000,
      payables: [{ id: 926, supplier: 'Agarwal Traders', amount: 22000 }],
      balance_p10: -7000,
      balance_p50: -2000,
      balance_p90: 3000,
      below_buffer: true,
    },
  ],
  flagged_days: [{ date: '2026-11-20', lowest_balance_p10: -7000, gap: 12000 }],
  shortfalls: [
    {
      date: '2026-11-20',
      date_text: '20 Nov (Friday)',
      days_ahead: 5,
      last_day: '2026-11-21',
      n_days: 2,
      lowest_balance_p10: -7000,
      gap: 12000,
      cause: { payable_id: 926, supplier: 'Agarwal Traders', amount: 22000, due_date: '2026-11-20' },
      fix: {
        payable_id: 926,
        move_to: '2026-11-22',
        move_to_text: '22 Nov (Sunday)',
        days_later: 2,
        within_forecast: true,
        text: 'Agarwal Traders ka ₹22,000 payment 22 Nov (Sunday) ko karein to balance buffer se upar rahega.',
      },
    },
  ],
  summary_text: 'Agarwal Traders ka payment Friday ko balance buffer se neeche le ja sakta hai.',
  method: 'LightGBM quantile regression',
}

const BACKTEST_DATA = {
  window_days: 60,
  baseline_name: 'same-day-last-week',
  beats_baseline: true,
  mae_improvement_pct: 34.0,
  model: { mae: 3438 },
  baseline: { mae: 5212 },
}

function fakeApi(overrides = {}) {
  return {
    status: vi.fn().mockResolvedValue({ llm: 'fallback', voice: 'browser', now: '2026-11-15T08:30:00' }),
    radar: vi.fn().mockResolvedValue(RADAR_DATA),
    backtest: vi.fn().mockResolvedValue(BACKTEST_DATA),
    draftReschedule: vi.fn().mockResolvedValue({ pending_actions: [{ id: 99, kind: 'reschedule_payable' }] }),
    actions: vi.fn().mockResolvedValue([]),
    soundboxEvents: vi.fn().mockResolvedValue([]),
    ...overrides,
  }
}

describe('CashRadar Page', () => {
  it('renders balance, shortfall and forecast tiles', async () => {
    const api = fakeApi()
    render(
      <AppProvider api={api} pollMs={0}>
        <MemoryRouter>
          <CashRadar />
        </MemoryRouter>
      </AppProvider>,
    )

    expect(await screen.findByText('Cash Radar')).toBeInTheDocument()
    expect(await screen.findByText('₹16,000')).toBeInTheDocument()
    expect(screen.getByText(/Kami: 20 Nov \(Friday\)/)).toBeInTheDocument()
    expect(screen.getByText(/Agarwal Traders ka ₹22,000 payment 22 Nov/)).toBeInTheDocument()
  })

  it('clicking shift button calls draftReschedule and triggers approval', async () => {
    const api = fakeApi()
    render(
      <AppProvider api={api} pollMs={0}>
        <MemoryRouter>
          <CashRadar />
        </MemoryRouter>
      </AppProvider>,
    )

    const shiftBtn = await screen.findByRole('button', { name: /22 Nov \(Sunday\) ko shift karein/i })
    fireEvent.click(shiftBtn)

    await waitFor(() => {
      expect(api.draftReschedule).toHaveBeenCalledWith(926, '2026-11-22')
    })
  })

  it('toggling table view shows tabular data', async () => {
    const api = fakeApi()
    render(
      <AppProvider api={api} pollMs={0}>
        <MemoryRouter>
          <CashRadar />
        </MemoryRouter>
      </AppProvider>,
    )

    const tableToggle = await screen.findByRole('button', { name: /Table view/i })
    fireEvent.click(tableToggle)

    expect(screen.getByText('Din')).toBeInTheDocument()
    expect(screen.getByText(/15 Nov Sun/)).toBeInTheDocument()
    expect(screen.getByText(/20 Nov Fri/)).toBeInTheDocument()
  })
})

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import DemoBar from '../components/DemoBar'
import { AppProvider, useApp } from '../context/AppContext'

function fakeApi(overrides = {}) {
  return {
    status: vi.fn().mockResolvedValue({ llm: 'fallback', voice: 'browser', now: '2026-11-15T08:30:00' }),
    demoState: vi.fn().mockResolvedValue({ day: 0, pending_actions: 0, open_udhaar: 10 }),
    reset: vi.fn().mockResolvedValue({ demo_date: '2026-11-15' }),
    jumpToFriday: vi.fn().mockResolvedValue({ tick: { reminders: [{ auto_sent: true }, { auto_sent: false }] } }),
    actions: vi.fn().mockResolvedValue([{ id: 9, status: 'pending', kind: 'send_reminder' }]),
    simulatePayment: vi.fn().mockResolvedValue({ soundbox_text: 'Paytm par 650 rupaye mile', soundbox_event_id: 3, settled_udhaar: { customer: 'Sunita' } }),
    speak: vi.fn().mockResolvedValue(null),
    briefing: vi.fn().mockResolvedValue({ spoken_text: 'Namaste' }),
    soundboxEvents: vi.fn().mockResolvedValue([]),
    ...overrides,
  }
}

function QueueProbe() {
  const { approvalQueue } = useApp()
  return <p data-testid="queue">{approvalQueue.map((a) => a.id).join(',')}</p>
}

function setup(api) {
  window.speechSynthesis = undefined
  return render(
    <AppProvider api={api} pollMs={0}>
      <MemoryRouter>
        <DemoBar />
        <QueueProbe />
      </MemoryRouter>
    </AppProvider>,
  )
}

describe('DemoBar', () => {
  it('shows demo state', async () => {
    setup(fakeApi())
    expect(await screen.findByText(/Day 0 · 0 pending · 10 udhaar open/)).toBeInTheDocument()
  })

  it('reset calls the backend', async () => {
    const api = fakeApi()
    setup(api)
    fireEvent.click(screen.getByRole('button', { name: /Reset/ }))
    expect(await screen.findByText(/Reset · demo date 2026-11-15/)).toBeInTheDocument()
    expect(api.reset).toHaveBeenCalledOnce()
  })

  it('jump to Friday queues pending reminders for approval', async () => {
    setup(fakeApi())
    fireEvent.click(screen.getByRole('button', { name: /Jump to Friday/ }))
    expect(await screen.findByText(/1 reminder preview, 1 awaiting approval/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('queue')).toHaveTextContent('9'))
  })

  it('simulated payment reports the closed udhaar', async () => {
    const api = fakeApi()
    setup(api)
    fireEvent.click(screen.getByRole('button', { name: /Sunita pays 650/ }))
    expect(await screen.findByText(/Sunita: udhaar closed/)).toBeInTheDocument()
    expect(api.simulatePayment).toHaveBeenCalledWith(650, 'Sunita')
  })
})

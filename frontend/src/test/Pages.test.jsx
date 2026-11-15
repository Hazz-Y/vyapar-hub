// Renders each data page with real API responses (captured from the seeded demo backend),
// so a field-name mismatch between the UI and the API fails here instead of on stage.
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { AppProvider } from '../context/AppContext'
import Growth from '../pages/Growth'
import Settings from '../pages/Settings'
import Suppliers from '../pages/Suppliers'
import Udhaar from '../pages/Udhaar'
import growth from './fixtures/growth.json'
import matching from './fixtures/matching.json'
import merchant from './fixtures/merchant.json'
import payables from './fixtures/payables.json'
import settings from './fixtures/settings.json'
import status from './fixtures/status.json'
import udhaar from './fixtures/udhaar.json'

function api() {
  const ok = (v) => vi.fn().mockResolvedValue(v)
  return {
    status: ok(status), merchant: ok(merchant), settings: ok(settings), udhaar: ok(udhaar), messages: ok([]),
    growth: ok(growth), payables: ok(payables), matching: ok(matching), soundboxEvents: ok([]),
    gstExportUrl: (m) => `/gst?month=${m}`,
  }
}

function renderPage(Page) {
  return render(
    <AppProvider api={api()} pollMs={0}>
      <MemoryRouter>
        <Page />
      </MemoryRouter>
    </AppProvider>,
  )
}

describe('pages render real API data', () => {
  it('Udhaar shows server totals and entries', async () => {
    renderPage(Udhaar)
    const first = udhaar.entries[0]
    expect(await screen.findByText(first.display_name)).toBeInTheDocument()
    expect(screen.getByText(`${udhaar.totals.open_count} log`)).toBeInTheDocument()
  })

  it('Growth shows lapsed regulars, peak slot and festival', async () => {
    renderPage(Growth)
    expect(await screen.findByText(`${growth.lapsed_regulars.count} regulars 3 hafte se nahi aaye`)).toBeInTheDocument()
    expect(screen.getByText(growth.lapsed_regulars.customers[0].name)).toBeInTheDocument()
    expect(screen.getByText(growth.peak_hours.peak_slot.label)).toBeInTheDocument()
    expect(screen.getByRole('table', { name: /weekday and hour/ })).toBeInTheDocument()
  })

  it('Suppliers shows supplier names and the matching summary', async () => {
    renderPage(Suppliers)
    expect((await screen.findAllByText(payables[0].supplier)).length).toBeGreaterThan(0)
    expect(screen.getByText(/names matched/)).toBeInTheDocument()
  })

  it('Settings shows the merchant and autonomy toggles', async () => {
    renderPage(Settings)
    expect(await screen.findByText(merchant.name)).toBeInTheDocument()
    expect(screen.getByLabelText('Toggle Udhaar reminders')).toBeInTheDocument()
  })
})

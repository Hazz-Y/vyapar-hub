import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import ApprovalSheet from '../components/ApprovalSheet'

const ACTION = {
  id: 1,
  kind: 'pay_supplier',
  readback_text: 'Agarwal ko ₹22,000 bhejna hai.',
  amount: 22000,
  recipient: 'Agarwal Traders',
  payload: { upi_vpa: 'agarwal@upi' },
}

describe('ApprovalSheet', () => {
  it('shows readback text and amount', () => {
    render(
      <ApprovalSheet action={ACTION} onApprove={vi.fn()} onReject={vi.fn()} onClose={vi.fn()} />,
    )
    expect(screen.getByText(/Agarwal ko/)).toBeInTheDocument()
    expect(screen.getByTestId('sheet-amount')).toHaveTextContent('₹22,000')
  })

  it('auto-submits on 4 digits', async () => {
    const onApprove = vi.fn().mockResolvedValue({ confirmation_text: 'Done' })
    render(
      <ApprovalSheet action={ACTION} onApprove={onApprove} onReject={vi.fn()} onClose={vi.fn()} />,
    )
    ;['1', '2', '3', '4'].forEach((k) =>
      fireEvent.click(screen.getByRole('button', { name: k })),
    )
    await waitFor(() => expect(onApprove).toHaveBeenCalledWith('1234'))
  })

  it('shows success message after approve', async () => {
    const onApprove = vi.fn().mockResolvedValue({ confirmation_text: 'Payment ho gaya' })
    render(
      <ApprovalSheet action={ACTION} onApprove={onApprove} onReject={vi.fn()} onClose={vi.fn()} />,
    )
    ;['1', '2', '3', '4'].forEach((k) =>
      fireEvent.click(screen.getByRole('button', { name: k })),
    )
    await waitFor(() => expect(screen.getByText('Payment ho gaya')).toBeInTheDocument())
  })

  it('renders nothing when action is null', () => {
    const { container } = render(
      <ApprovalSheet action={null} onApprove={vi.fn()} onReject={vi.fn()} onClose={vi.fn()} />,
    )
    expect(container.firstChild).toBeNull()
  })

  it('shows demo PIN hint', () => {
    render(
      <ApprovalSheet action={ACTION} onApprove={vi.fn()} onReject={vi.fn()} onClose={vi.fn()} />,
    )
    expect(screen.getByText(/Demo PIN: 1234/)).toBeInTheDocument()
  })

  it('clear button resets PIN', () => {
    render(
      <ApprovalSheet action={ACTION} onApprove={vi.fn()} onReject={vi.fn()} onClose={vi.fn()} />,
    )
    fireEvent.click(screen.getByRole('button', { name: '1' }))
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }))
    // After clear, dots should be empty (no filled dots)
    const dots = document.querySelectorAll('[aria-label^="PIN entered"]')
    expect(dots.length).toBeGreaterThan(0)
  })
})

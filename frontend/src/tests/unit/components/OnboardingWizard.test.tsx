import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { OnboardingWizard } from '@/components/wizard/OnboardingWizard'

vi.mock('@/services/agents', () => ({
  agentsService: {
    create: vi.fn().mockResolvedValue({ id: 'ag-1', name: 'Agent', api_key: 'key_abc', last_heartbeat_at: null }),
    list: vi.fn().mockResolvedValue([]),
  },
}))

describe('OnboardingWizard', () => {
  const onComplete = vi.fn()

  beforeEach(() => vi.clearAllMocks())

  it('renders welcome screen (step 0) on mount', () => {
    render(<OnboardingWizard onComplete={onComplete} />)
    expect(screen.getByText(/Bem-vindo/i)).toBeInTheDocument()
  })

  it('advances to next step when Começar button clicked', () => {
    render(<OnboardingWizard onComplete={onComplete} />)
    fireEvent.click(screen.getByText(/Começar/i))
    // Step 1 = Instância
    expect(screen.getByText(/Instância/i)).toBeInTheDocument()
  })

  it('shows step indicators', () => {
    render(<OnboardingWizard onComplete={onComplete} />)
    // Should show step dots
    const steps = screen.getAllByRole('button').filter((b) => b.className.includes('rounded-full'))
    expect(steps.length).toBeGreaterThan(0)
  })
})

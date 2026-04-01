import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { AddCameraWizard } from '@/components/wizard/AddCameraWizard'

vi.mock('@/services/cameras', () => ({
  camerasService: {
    create: vi.fn().mockResolvedValue({ id: 'cam-1' }),
    list: vi.fn().mockResolvedValue([]),
    onvifProbe: vi.fn().mockResolvedValue({ streams: [] }),
  },
}))
vi.mock('@/services/agents', () => ({
  agentsService: { list: vi.fn().mockResolvedValue([]) },
}))
vi.mock('@/services/analytics', () => ({
  analyticsService: { createROI: vi.fn().mockResolvedValue({}) },
}))

describe('AddCameraWizard', () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
    onCreated: vi.fn(),
  }

  beforeEach(() => vi.clearAllMocks())

  it('renders protocol selection on step 0', () => {
    render(<AddCameraWizard {...defaultProps} />)
    expect(screen.getByText('RTSP via Agent')).toBeInTheDocument()
    expect(screen.getByText('RTMP Push')).toBeInTheDocument()
    expect(screen.getByText('ONVIF')).toBeInTheDocument()
  })

  it('advances to next step when protocol selected and Next clicked', async () => {
    render(<AddCameraWizard {...defaultProps} />)
    fireEvent.click(screen.getByText('Próximo'))
    await waitFor(() => {
      expect(screen.queryByText('RTMP Push')).not.toBeInTheDocument()
    })
  })

  it('defaults to provided protocol', () => {
    render(<AddCameraWizard {...defaultProps} defaultProtocol="rtmp_push" />)
    // RTMP push card should be visually selected (has accent background)
    expect(screen.getByText('RTMP Push')).toBeInTheDocument()
  })

  it('does not render when open=false', () => {
    render(<AddCameraWizard {...defaultProps} open={false} />)
    expect(screen.queryByText('RTSP via Agent')).not.toBeInTheDocument()
  })
})

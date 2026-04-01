import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { VideoPlayer } from '@/components/camera/VideoPlayer'

// Mock HLS.js
vi.mock('hls.js', () => ({
  default: {
    isSupported: () => false,
    Events: { MANIFEST_PARSED: 'hlsManifestParsed', ERROR: 'hlsError' },
  },
}))

describe('VideoPlayer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders without source — shows "not configured" state', () => {
    render(<VideoPlayer />)
    expect(screen.getByText('Câmera não configurada')).toBeInTheDocument()
  })

  it('renders camera name overlay when name prop provided', () => {
    render(<VideoPlayer src="http://example.com/stream.m3u8" name="Câmera 01" />)
    expect(screen.getByText('Câmera 01')).toBeInTheDocument()
  })

  it('shows "Sem sinal" when error prop is triggered via onError', () => {
    const onError = vi.fn()
    const { container } = render(
      <VideoPlayer src="invalid" onError={onError} />,
    )
    // Simulate video error event
    const video = container.querySelector('video')!
    video.dispatchEvent(new Event('error'))
    // After error, "Sem sinal" should appear
    expect(screen.queryByText('Câmera não configurada')).not.toBeInTheDocument()
  })

  it('applies className to container', () => {
    const { container } = render(<VideoPlayer className="aspect-video" />)
    expect(container.firstChild).toHaveClass('aspect-video')
  })
})

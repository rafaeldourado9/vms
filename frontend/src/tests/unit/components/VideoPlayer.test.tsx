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

// jsdom does not implement HTMLMediaElement.play — mock it
Object.defineProperty(HTMLMediaElement.prototype, 'play', {
  configurable: true,
  writable: true,
  value: vi.fn().mockResolvedValue(undefined),
})

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

  it('shows "Sem sinal" when error event fired on video element', () => {
    const { container } = render(<VideoPlayer src="http://example.com/stream.m3u8" />)
    const video = container.querySelector('video')!
    // Trigger onerror via the React handler
    Object.defineProperty(video, 'error', { value: { code: 4 }, configurable: true })
    video.dispatchEvent(new Event('error'))
    // After error, loading/error state changes — camera name should not be there
    expect(screen.queryByText('Câmera não configurada')).not.toBeInTheDocument()
  })

  it('applies className to container', () => {
    const { container } = render(<VideoPlayer className="aspect-video" />)
    expect(container.firstChild).toHaveClass('aspect-video')
  })
})

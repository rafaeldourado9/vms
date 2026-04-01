import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSSE } from '@/hooks/useSSE'

// Mock authStore to return a token
vi.mock('@/store/authStore', () => ({
  useAuthStore: (selector: (s: { tokens: { access_token: string } | null }) => unknown) =>
    selector({ tokens: { access_token: 'test-token' } }),
}))

// Mock EventSource
class MockEventSource {
  static instances: MockEventSource[] = []
  url: string
  onopen: (() => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onerror: (() => void) | null = null
  closed = false

  constructor(url: string) {
    this.url = url
    MockEventSource.instances.push(this)
  }
  close() { this.closed = true }
}

describe('useSSE', () => {
  let OrigEventSource: typeof EventSource

  beforeEach(() => {
    OrigEventSource = global.EventSource
    // @ts-expect-error mock
    global.EventSource = MockEventSource
    MockEventSource.instances = []
    vi.useFakeTimers()
  })

  afterEach(() => {
    global.EventSource = OrigEventSource
    vi.useRealTimers()
  })

  it('starts disconnected, connects when token present', () => {
    const { result } = renderHook(() => useSSE())
    expect(result.current.connected).toBe(false)

    const es = MockEventSource.instances[0]
    act(() => { es.onopen?.() })

    expect(result.current.connected).toBe(true)
  })

  it('parses JSON message and exposes as lastEvent', () => {
    const { result } = renderHook(() => useSSE())
    const es = MockEventSource.instances[0]
    act(() => { es.onopen?.() })

    act(() => {
      es.onmessage?.({ data: JSON.stringify({ event: 'camera.online', camera_id: 'cam1' }) })
    })

    expect(result.current.lastEvent).toMatchObject({ event: 'camera.online' })
  })

  it('reconnects after error with backoff', () => {
    const { result } = renderHook(() => useSSE())
    const es = MockEventSource.instances[0]
    act(() => { es.onopen?.() })

    act(() => { es.onerror?.() })
    expect(result.current.connected).toBe(false)

    // advance timer to trigger reconnect
    act(() => { vi.advanceTimersByTime(1100) })
    expect(MockEventSource.instances.length).toBe(2)
  })
})

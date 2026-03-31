import { useEffect, useRef, useState } from 'react'
import { useAuthStore } from '@/store/authStore'

interface SSEState {
  lastEvent: Record<string, unknown> | null
  connected: boolean
}

export function useSSE(): SSEState {
  const token = useAuthStore((s) => s.tokens?.access_token)
  const [connected, setConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState<Record<string, unknown> | null>(null)
  const esRef = useRef<EventSource | null>(null)
  const backoffRef = useRef(1000)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!token) return

    const connect = () => {
      esRef.current?.close()
      const es = new EventSource(`/api/v1/sse?token=${encodeURIComponent(token)}`)
      esRef.current = es

      es.onopen = () => {
        setConnected(true)
        backoffRef.current = 1000
      }

      es.onmessage = (e: MessageEvent<string>) => {
        try {
          const data = JSON.parse(e.data) as Record<string, unknown>
          setLastEvent(data)
        } catch {
          // non-JSON heartbeat
        }
      }

      es.onerror = () => {
        setConnected(false)
        es.close()
        timerRef.current = setTimeout(() => {
          backoffRef.current = Math.min(backoffRef.current * 2, 30000)
          connect()
        }, backoffRef.current)
      }
    }

    connect()

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      esRef.current?.close()
      setConnected(false)
    }
  }, [token])

  return { lastEvent, connected }
}

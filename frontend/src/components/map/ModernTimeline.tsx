import { useState, useRef, useMemo, useCallback, useEffect } from 'react'
import type { RecordingSegment } from '@/types'

interface ModernTimelineProps {
  segments: RecordingSegment[]
  currentTime: Date
  onSeek: (time: Date) => void
  isLoading: boolean
  selectedDate: string
  onClipSelect?: (start: Date, end: Date) => void
}

function fmt(ms: number) {
  return new Date(ms).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

export function ModernTimeline({
  segments,
  currentTime,
  onSeek,
  isLoading,
}: ModernTimelineProps) {
  const trackRef   = useRef<HTMLDivElement>(null)
  const isDragging = useRef(false)

  const [thumbPct, setThumbPct] = useState(0)
  const [hoverPct, setHoverPct] = useState<number | null>(null)
  const [dragging, setDragging] = useState(false)

  // Range = first segment start → last segment end (fallback to full day if no segments)
  const { rangeStart, rangeEnd } = useMemo(() => {
    if (segments.length === 0) {
      const base = new Date().setHours(0, 0, 0, 0)
      return { rangeStart: base, rangeEnd: base + 24 * 60 * 60 * 1000 }
    }
    const starts = segments.map(s => new Date(s.started_at).getTime())
    const ends   = segments.map(s => new Date(s.ended_at).getTime())
    return {
      rangeStart: Math.min(...starts),
      rangeEnd:   Math.max(...ends),
    }
  }, [segments])

  const rangeMs = rangeEnd - rangeStart

  // Sync thumb with currentTime (skip while dragging)
  useEffect(() => {
    if (isDragging.current) return
    const pct = Math.max(0, Math.min(1, (currentTime.getTime() - rangeStart) / rangeMs))
    setThumbPct(pct)
  }, [currentTime, rangeStart, rangeMs])

  const pctFromEvent = useCallback((e: MouseEvent | React.MouseEvent) => {
    if (!trackRef.current) return 0
    const rect = trackRef.current.getBoundingClientRect()
    return Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  }, [])

  const seekToPct = useCallback((pct: number) => {
    onSeek(new Date(rangeStart + pct * rangeMs))
  }, [rangeStart, rangeMs, onSeek])

  const handleTrackMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDragging.current = true
    setDragging(true)

    const pct = pctFromEvent(e)
    setThumbPct(pct)
    seekToPct(pct)

    const onMove = (ev: MouseEvent) => {
      const p = pctFromEvent(ev)
      setThumbPct(p)
      seekToPct(p)
    }
    const onUp = (ev: MouseEvent) => {
      isDragging.current = false
      setDragging(false)
      const p = pctFromEvent(ev)
      setThumbPct(p)
      seekToPct(p)
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }, [pctFromEvent, seekToPct])

  const thumbMs = rangeStart + thumbPct * rangeMs
  const hoverMs = hoverPct != null ? rangeStart + hoverPct * rangeMs : null

  const totalDurationMin = useMemo(() =>
    Math.round(segments.reduce((a, s) => a + s.duration_seconds, 0) / 60),
    [segments])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-10 text-xs text-zinc-500">
        Carregando…
      </div>
    )
  }

  return (
    <div className="space-y-1.5">
      {/* Time labels: range start / current / range end */}
      <div className="flex items-center justify-between text-[10px] text-zinc-500 tabular-nums">
        <span>{fmt(rangeStart)}</span>
        <span className="font-medium text-zinc-300">{fmt(thumbMs)}</span>
        <span>{fmt(rangeEnd)}</span>
      </div>

      {/* Track */}
      <div
        ref={trackRef}
        className="relative h-5 flex items-center"
        style={{ cursor: dragging ? 'grabbing' : 'pointer' }}
        onMouseDown={handleTrackMouseDown}
        onMouseMove={e => setHoverPct(pctFromEvent(e))}
        onMouseLeave={() => setHoverPct(null)}
      >
        {/* Rail */}
        <div className="absolute inset-x-0 h-1.5 rounded-full" style={{ background: '#27272a' }} />

        {/* Segment fills — positioned relative to rangeStart */}
        {segments.map(seg => {
          const s0 = new Date(seg.started_at).getTime()
          const s1 = new Date(seg.ended_at).getTime()
          const l  = ((s0 - rangeStart) / rangeMs) * 100
          const w  = ((s1 - s0) / rangeMs) * 100
          const isMotion = seg.event_type === 'motion'
          const isEvent  = seg.event_type === 'event'
          return (
            <div
              key={seg.id}
              className="absolute h-1.5 rounded-full"
              style={{
                left:       `${l}%`,
                width:      `${Math.max(0.2, w)}%`,
                background: isMotion ? '#d97706' : isEvent ? '#dc2626' : '#3b82f6',
              }}
            />
          )
        })}

        {/* Progress fill: rangeStart → thumb */}
        <div
          className="absolute h-1.5 rounded-full pointer-events-none"
          style={{ left: 0, width: `${thumbPct * 100}%`, background: 'rgba(59,130,246,0.3)' }}
        />

        {/* Hover hair */}
        {hoverPct != null && (
          <div
            className="absolute w-px h-3 pointer-events-none"
            style={{ left: `${hoverPct * 100}%`, background: 'rgba(255,255,255,0.18)' }}
          />
        )}

        {/* Thumb */}
        <div
          className="absolute w-4 h-4 rounded-full border-2 border-blue-500 -translate-x-1/2 z-10 pointer-events-none"
          style={{
            left:       `${thumbPct * 100}%`,
            background: '#fff',
            boxShadow:  dragging ? '0 0 0 3px rgba(59,130,246,0.4)' : '0 1px 4px rgba(0,0,0,0.5)',
          }}
        />

        {/* Hover tooltip */}
        {hoverPct != null && hoverMs != null && (
          <div
            className="absolute -top-6 text-[10px] tabular-nums -translate-x-1/2 pointer-events-none font-mono px-1 rounded"
            style={{ left: `${hoverPct * 100}%`, color: '#d4d4d8', background: 'rgba(0,0,0,0.7)' }}
          >
            {fmt(hoverMs)}
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-[10px] text-zinc-600">
        <span>{segments.length} seg · {totalDurationMin}min</span>
        <span className="flex items-center gap-1.5 ml-auto">
          <span className="w-2 h-1 rounded-sm" style={{ background: '#3b82f6' }} /> Contínuo
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-1 rounded-sm" style={{ background: '#d97706' }} /> Movimento
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-1 rounded-sm" style={{ background: '#dc2626' }} /> Evento
        </span>
      </div>
    </div>
  )
}

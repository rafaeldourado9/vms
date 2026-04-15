import { useState, useRef, useMemo, useCallback, useEffect } from 'react'
import type { RecordingSegment } from '@/types'
import { SEV_COLOR } from '@/constants/plugins'

export interface EventMarker {
  id: string
  time: Date
  severity: 'critical' | 'warning' | 'info'
  plugin_id: string
  event_type: string
}

interface ModernTimelineProps {
  segments: RecordingSegment[]
  currentTime: Date
  onSeek: (time: Date) => void
  isLoading: boolean
  selectedDate: string
  eventMarkers?: EventMarker[]
}

function fmt(ms: number, showSeconds = false) {
  return new Date(ms).toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
    ...(showSeconds ? { second: '2-digit' } : {}),
  })
}

/** Escolhe o intervalo de tick (ms) de acordo com a janela visível */
function tickInterval(viewMs: number): number {
  if (viewMs <= 30 * 60 * 1000)     return 5  * 60 * 1000   // 5 min
  if (viewMs <= 2  * 3600 * 1000)   return 15 * 60 * 1000   // 15 min
  if (viewMs <= 6  * 3600 * 1000)   return 30 * 60 * 1000   // 30 min
  return 60 * 60 * 1000                                       // 1 h
}

const DAY_MS = 24 * 3600 * 1000

export function ModernTimeline({
  segments,
  currentTime,
  onSeek,
  isLoading,
  selectedDate,
  eventMarkers,
}: ModernTimelineProps) {
  const trackRef   = useRef<HTMLDivElement>(null)
  const isDragging = useRef(false)

  // Janela visível: usa o dia selecionado como base (00:00 - 23:59)
  const dayStart = useMemo(() => {
    return new Date(selectedDate + 'T00:00:00').getTime()
  }, [selectedDate])

  // Calcula range dos segmentos para highlight de cobertura
  const { rangeStart, rangeEnd } = useMemo(() => {
    if (segments.length === 0) {
      return { rangeStart: dayStart, rangeEnd: dayStart + DAY_MS }
    }
    const starts = segments.map(s => new Date(s.started_at).getTime())
    const ends   = segments.map(s => new Date(s.ended_at).getTime())
    return { rangeStart: Math.min(dayStart, Math.min(...starts)), rangeEnd: Math.min(dayStart + DAY_MS, Math.max(...ends)) }
  }, [segments, dayStart])

  const viewMs = DAY_MS
  const rangeMs = rangeEnd - rangeStart

  // Ticks de minutagem
  const ticks = useMemo(() => {
    const interval = tickInterval(viewMs)
    const result: { ms: number; pct: number }[] = []
    const first = Math.ceil(dayStart / interval) * interval
    for (let ms = first; ms <= dayStart + viewMs; ms += interval) {
      result.push({ ms, pct: (ms - dayStart) / viewMs })
    }
    return result
  }, [dayStart, viewMs])

  // Playhead position
  useEffect(() => {
    if (isDragging.current) return
    const pct = Math.max(0, Math.min(1, (currentTime.getTime() - dayStart) / viewMs))
    setThumbPct(pct)
  }, [currentTime, dayStart, viewMs])

  const [thumbPct, setThumbPct] = useState(0)
  const [hoverPct, setHoverPct] = useState<number | null>(null)
  const [dragging, setDragging] = useState(false)

  const pctFromEvent = useCallback((e: MouseEvent | React.MouseEvent) => {
    if (!trackRef.current) return 0
    const rect = trackRef.current.getBoundingClientRect()
    return Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width))
  }, [])

  const seekToPct = useCallback((pct: number) => {
    onSeek(new Date(dayStart + pct * viewMs))
  }, [dayStart, viewMs, onSeek])

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
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

  // Highlight de cobertura (onde tem gravação)
  const coveragePct = useMemo(() => {
    if (rangeMs <= 0) return null
    const l = ((rangeStart - dayStart) / viewMs) * 100
    const w = ((rangeEnd - rangeStart) / viewMs) * 100
    return { left: l, width: w }
  }, [rangeStart, rangeEnd, dayStart, viewMs, rangeMs])

  const thumbMs = dayStart + thumbPct * viewMs
  const hoverMs = hoverPct != null ? dayStart + hoverPct * viewMs : null

  if (isLoading) return (
    <div className="h-12 flex items-center justify-center text-[11px]" style={{ color: '#3f3f46' }}>
      Carregando…
    </div>
  )

  return (
    <div
      ref={trackRef}
      className="relative select-none"
      style={{ height: 48, cursor: dragging ? 'grabbing' : 'crosshair' }}
      onMouseDown={handleMouseDown}
      onMouseMove={e => setHoverPct(pctFromEvent(e))}
      onMouseLeave={() => setHoverPct(null)}
    >
      {/* ── Rail (fundo da timeline) ── */}
      <div
        className="absolute inset-x-0 pointer-events-none"
        style={{ top: 16, height: 18, background: 'var(--elevated)', borderRadius: 4 }}
      />

      {/* ── Highlight de cobertura (onde tem gravação) ── */}
      {coveragePct && coveragePct.width > 0.1 && (
        <div
          className="absolute pointer-events-none"
          style={{
            top: 16,
            height: 18,
            borderRadius: 4,
            left: `${coveragePct.left}%`,
            width: `${Math.min(100, coveragePct.width)}%`,
            background: '#14b8a6',
            opacity: 0.15,
          }}
        />
      )}

      {/* ── Event markers (acima do rail) ── */}
      {eventMarkers?.map(marker => {
        const pct = ((marker.time.getTime() - dayStart) / viewMs) * 100
        if (pct < 0 || pct > 100) return null
        const color = SEV_COLOR[marker.severity] ?? '#60a5fa'
        return (
          <div
            key={marker.id}
            className="absolute pointer-events-none"
            style={{
              left: `${pct}%`,
              top: 9,
              transform: 'translateX(-50%)',
              width: 1.5,
              height: 5,
              background: color,
              opacity: 0.8,
              borderRadius: 1,
            }}
            title={`${marker.event_type} · ${marker.plugin_id}`}
          />
        )
      })}

      {/* ── Ticks de minutagem (dentro do rail) ── */}
      {ticks.map(({ ms, pct }) => {
        const d = new Date(ms)
        const isHour = d.getMinutes() === 0
        return (
          <div key={ms} className="absolute pointer-events-none" style={{ left: `${pct * 100}%` }}>
            {/* traço */}
            <div
              style={{
                position: 'absolute',
                top: 16,
                left: 0,
                transform: 'translateX(-50%)',
                width: 1,
                height: isHour ? 8 : 4,
                background: isHour ? 'var(--text-3)' : 'var(--border)',
              }}
            />
            {/* label */}
            <div
              style={{
                position: 'absolute',
                top: 26,
                left: 0,
                transform: 'translateX(-50%)',
                fontSize: 9,
                fontFamily: 'monospace',
                color: isHour ? 'var(--text-2)' : 'var(--text-3)',
                fontWeight: isHour ? 500 : 400,
                whiteSpace: 'nowrap',
              }}
            >
              {fmt(ms)}
            </div>
          </div>
        )
      })}

      {/* ── Playhead ── */}
      <div
        className="absolute pointer-events-none"
        style={{
          left: `${thumbPct * 100}%`,
          top: 0,
          bottom: 0,
          transform: 'translateX(-50%)',
          width: 2,
          background: '#ef4444',
          zIndex: 10,
        }}
      >
        {/* triângulo no topo */}
        <div
          style={{
            position: 'absolute',
            top: -5,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 0,
            height: 0,
            borderLeft: '4px solid transparent',
            borderRight: '4px solid transparent',
            borderTop: '5px solid #ef4444',
          }}
        />
      </div>

      {/* ── Playhead time label ── */}
      <div
        className="absolute pointer-events-none tabular-nums"
        style={{
          left: `${thumbPct * 100}%`,
          top: 0,
          transform: 'translateX(-50%)',
          fontSize: 9,
          fontFamily: 'monospace',
          padding: '1px 4px',
          borderRadius: 3,
          background: 'rgba(239,68,68,0.9)',
          color: '#fff',
          whiteSpace: 'nowrap',
          fontWeight: 600,
          zIndex: 11,
        }}
      >
        {fmt(thumbMs)}
      </div>

      {/* ── Hover ghost + tooltip ── */}
      {hoverPct != null && (
        <>
          <div
            className="absolute pointer-events-none"
            style={{
              left: `${hoverPct * 100}%`,
              top: 16,
              bottom: 0,
              width: 1,
              background: 'rgba(255,255,255,0.15)',
            }}
          />
          {Math.abs(hoverPct - thumbPct) > 0.02 && (
            <div
              className="absolute pointer-events-none tabular-nums"
              style={{
                left: `${hoverPct * 100}%`,
                top: 0,
                transform: 'translateX(-50%)',
                fontSize: 9,
                fontFamily: 'monospace',
                padding: '1px 4px',
                borderRadius: 3,
                background: 'rgba(40,40,40,0.9)',
                color: '#a3a3a3',
                whiteSpace: 'nowrap',
                zIndex: 11,
              }}
            >
              {fmt(hoverMs!)}
            </div>
          )}
        </>
      )}
    </div>
  )
}

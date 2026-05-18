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

function fmt(ms: number) {
  return new Date(ms).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

function tickInterval(viewMs: number): number {
  if (viewMs <= 30 * 60 * 1000)   return 5  * 60 * 1000
  if (viewMs <= 2  * 3600 * 1000) return 15 * 60 * 1000
  if (viewMs <= 6  * 3600 * 1000) return 30 * 60 * 1000
  return 60 * 60 * 1000
}

const DAY_MS = 24 * 3600 * 1000
const RAIL_H = 24
const RAIL_TOP = 18

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

  const dayStart = useMemo(
    () => new Date(selectedDate + 'T00:00:00').getTime(),
    [selectedDate],
  )

  const viewMs = DAY_MS

  const ticks = useMemo(() => {
    const interval = tickInterval(viewMs)
    const result: { ms: number; pct: number }[] = []
    const first = Math.ceil(dayStart / interval) * interval
    for (let ms = first; ms <= dayStart + viewMs; ms += interval) {
      result.push({ ms, pct: (ms - dayStart) / viewMs })
    }
    return result
  }, [dayStart, viewMs])

  // Individual segment blocks
  const segBlocks = useMemo(() =>
    segments.map((seg) => {
      const s0  = new Date(seg.started_at).getTime()
      const s1  = new Date(seg.ended_at).getTime()
      const l   = Math.max(0, ((s0 - dayStart) / viewMs) * 100)
      const w   = Math.min(100 - l, ((s1 - s0) / viewMs) * 100)
      return { id: seg.id, left: l, width: Math.max(w, 0.15), seg }
    }),
  [segments, dayStart, viewMs])

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

  const thumbMs = dayStart + thumbPct * viewMs
  const hoverMs = hoverPct != null ? dayStart + hoverPct * viewMs : null

  if (isLoading) return (
    <div className="flex items-center justify-center" style={{ height: 56 }}>
      <div
        className="w-5 h-5 rounded-full border-t border-white/20 animate-spin"
        style={{ borderWidth: 1.5 }}
      />
    </div>
  )

  const totalH = RAIL_TOP + RAIL_H + 18 // rail + label space

  return (
    <div
      ref={trackRef}
      className="relative select-none"
      style={{ height: totalH, cursor: dragging ? 'grabbing' : 'crosshair' }}
      onMouseDown={handleMouseDown}
      onMouseMove={e => setHoverPct(pctFromEvent(e))}
      onMouseLeave={() => setHoverPct(null)}
    >
      {/* ── Rail background ── */}
      <div
        className="absolute inset-x-0 pointer-events-none"
        style={{
          top: RAIL_TOP,
          height: RAIL_H,
          background: 'rgba(255,255,255,0.04)',
          borderRadius: 6,
          border: '1px solid rgba(255,255,255,0.06)',
        }}
      />

      {/* ── Individual segment blocks ── */}
      {segBlocks.map(({ id, left, width }) => (
        <div
          key={id}
          className="absolute pointer-events-none"
          style={{
            top: RAIL_TOP + 2,
            height: RAIL_H - 4,
            borderRadius: 4,
            left:  `${left}%`,
            width: `${width}%`,
            background: 'linear-gradient(180deg, rgba(20,184,166,0.55) 0%, rgba(13,148,136,0.45) 100%)',
            border: '1px solid rgba(20,184,166,0.3)',
          }}
        />
      ))}

      {/* ── Playhead current-segment highlight ── */}
      {(() => {
        const hit = segBlocks.find(({ seg }) => {
          const s0 = new Date(seg.started_at).getTime()
          const s1 = new Date(seg.ended_at).getTime()
          return thumbMs >= s0 && thumbMs <= s1
        })
        if (!hit) return null
        return (
          <div
            className="absolute pointer-events-none"
            style={{
              top: RAIL_TOP + 2,
              height: RAIL_H - 4,
              borderRadius: 4,
              left:  `${hit.left}%`,
              width: `${hit.width}%`,
              background: 'linear-gradient(180deg, rgba(20,184,166,0.85) 0%, rgba(13,148,136,0.70) 100%)',
              border: '1px solid rgba(20,184,166,0.6)',
              boxShadow: '0 0 8px rgba(20,184,166,0.3)',
            }}
          />
        )
      })()}

      {/* ── Event markers ── */}
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
              top: RAIL_TOP - 5,
              transform: 'translateX(-50%)',
              width: 2,
              height: 6,
              background: color,
              opacity: 0.9,
              borderRadius: 1,
            }}
          />
        )
      })}

      {/* ── Hour ticks ── */}
      {ticks.map(({ ms, pct }) => {
        const d = new Date(ms)
        const isHour = d.getMinutes() === 0
        return (
          <div key={ms} className="absolute pointer-events-none" style={{ left: `${pct * 100}%` }}>
            <div
              style={{
                position: 'absolute',
                top: RAIL_TOP,
                left: 0,
                transform: 'translateX(-50%)',
                width: 1,
                height: isHour ? RAIL_H : Math.floor(RAIL_H / 2),
                background: isHour ? 'rgba(255,255,255,0.18)' : 'rgba(255,255,255,0.07)',
              }}
            />
            <div
              style={{
                position: 'absolute',
                top: RAIL_TOP + RAIL_H + 3,
                left: 0,
                transform: 'translateX(-50%)',
                fontSize: 9,
                fontFamily: 'monospace',
                color: isHour ? 'rgba(255,255,255,0.45)' : 'rgba(255,255,255,0.2)',
                fontWeight: isHour ? 500 : 400,
                whiteSpace: 'nowrap',
              }}
            >
              {fmt(ms)}
            </div>
          </div>
        )
      })}

      {/* ── Playhead line ── */}
      <div
        className="absolute pointer-events-none"
        style={{
          left: `${thumbPct * 100}%`,
          top: RAIL_TOP - 4,
          height: RAIL_H + 8,
          transform: 'translateX(-50%)',
          width: 2,
          background: '#ef4444',
          zIndex: 10,
          borderRadius: 1,
          boxShadow: '0 0 6px rgba(239,68,68,0.6)',
        }}
      />

      {/* ── Playhead thumb dot ── */}
      <div
        className="absolute pointer-events-none"
        style={{
          left: `${thumbPct * 100}%`,
          top: RAIL_TOP + RAIL_H / 2 - 5,
          transform: 'translateX(-50%)',
          width: 10,
          height: 10,
          borderRadius: '50%',
          background: '#ef4444',
          border: '2px solid rgba(255,255,255,0.85)',
          zIndex: 11,
          boxShadow: '0 0 8px rgba(239,68,68,0.7)',
        }}
      />

      {/* ── Playhead time label (above rail) ── */}
      <div
        className="absolute pointer-events-none tabular-nums"
        style={{
          left: `${thumbPct * 100}%`,
          top: RAIL_TOP - 18,
          transform: 'translateX(-50%)',
          fontSize: 9,
          fontFamily: 'monospace',
          padding: '1px 5px',
          borderRadius: 4,
          background: 'rgba(239,68,68,0.92)',
          color: '#fff',
          whiteSpace: 'nowrap',
          fontWeight: 600,
          zIndex: 12,
        }}
      >
        {fmt(thumbMs)}
      </div>

      {/* ── Hover ghost ── */}
      {hoverPct != null && (
        <>
          <div
            className="absolute pointer-events-none"
            style={{
              left: `${hoverPct * 100}%`,
              top: RAIL_TOP,
              height: RAIL_H,
              width: 1,
              background: 'rgba(255,255,255,0.2)',
            }}
          />
          {Math.abs(hoverPct - thumbPct) > 0.015 && (
            <div
              className="absolute pointer-events-none tabular-nums"
              style={{
                left: `${hoverPct * 100}%`,
                top: RAIL_TOP - 18,
                transform: 'translateX(-50%)',
                fontSize: 9,
                fontFamily: 'monospace',
                padding: '1px 5px',
                borderRadius: 4,
                background: 'rgba(30,30,40,0.92)',
                color: 'rgba(255,255,255,0.6)',
                whiteSpace: 'nowrap',
                zIndex: 12,
                border: '1px solid rgba(255,255,255,0.1)',
              }}
            >
              {fmt(hoverMs!)}
            </div>
          )}
        </>
      )}

      {/* ── Empty state label ── */}
      {segments.length === 0 && (
        <div
          className="absolute inset-x-0 pointer-events-none flex items-center justify-center"
          style={{ top: RAIL_TOP, height: RAIL_H, fontSize: 10, color: 'rgba(255,255,255,0.18)' }}
        >
          Sem gravações nesta data
        </div>
      )}
    </div>
  )
}

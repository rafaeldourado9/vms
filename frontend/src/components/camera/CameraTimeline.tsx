/**
 * CameraTimeline — barra de tempo minimalista estilo NVR.
 *
 * Mostra janela de 2h (padrão) com segmentos azuis, playhead vermelho
 * e labels de horário. Arrasta para panear, setas para navegar.
 */
import {
  useCallback, useEffect, useMemo, useRef, useState,
} from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import type { RecordingSegment } from '@/types'

interface Props {
  segments: RecordingSegment[]
  currentTime: Date          // posição do playhead
  date: string               // 'YYYY-MM-DD' — dia selecionado
  onSeek: (t: Date) => void
  onDateChange?: (d: string) => void
}

const VIEW_MS = 2 * 3600_000   // janela padrão: 2 horas
const TICK_INTERVAL_MS = 10 * 60_000  // label a cada 10 min

function pad(n: number) { return String(n).padStart(2, '0') }
function hhmm(ms: number) {
  const d = new Date(ms)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`
}
function isoDate(d: Date) { return d.toISOString().split('T')[0] }

export function CameraTimeline({ segments, currentTime, date, onSeek, onDateChange }: Props) {
  const trackRef   = useRef<HTMLDivElement>(null)
  const dragRef    = useRef({ dragging: false, startX: 0, startView: 0 })
  const didDragRef = useRef(false)

  // viewStart = início da janela visível (ms epoch)
  const [viewStart, setViewStart] = useState(() => {
    const now = currentTime.getTime()
    return now - VIEW_MS / 2
  })

  // Quando currentTime muda de fora (novo segmento selecionado), recentra
  useEffect(() => {
    if (dragRef.current.dragging) return
    setViewStart(currentTime.getTime() - VIEW_MS / 2)
  }, [currentTime])

  const clampView = useCallback((v: number) => {
    const dayStart = new Date(date + 'T00:00:00').getTime()
    const dayEnd   = dayStart + 24 * 3600_000
    return Math.max(dayStart - VIEW_MS / 4, Math.min(dayEnd - VIEW_MS * 3 / 4, v))
  }, [date])

  // ── Drag ──────────────────────────────────────────────────────────────────
  const onMouseDown = useCallback((e: React.MouseEvent) => {
    dragRef.current = { dragging: true, startX: e.clientX, startView: viewStart }
    didDragRef.current = false
    e.preventDefault()
  }, [viewStart])

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragRef.current.dragging || !trackRef.current) return
    const dx = e.clientX - dragRef.current.startX
    if (Math.abs(dx) > 3) didDragRef.current = true
    const rect = trackRef.current.getBoundingClientRect()
    const msPx = VIEW_MS / rect.width
    setViewStart(clampView(dragRef.current.startView - dx * msPx))
  }, [clampView])

  const onMouseUp = useCallback((e: React.MouseEvent) => {
    if (!dragRef.current.dragging) return
    dragRef.current.dragging = false
    if (!didDragRef.current && trackRef.current) {
      // click: seek
      const rect = trackRef.current.getBoundingClientRect()
      const pct  = (e.clientX - rect.left) / rect.width
      onSeek(new Date(viewStart + pct * VIEW_MS))
    }
  }, [viewStart, onSeek])

  const pan = useCallback((dir: -1 | 1) => {
    setViewStart(v => clampView(v + dir * VIEW_MS / 2))
  }, [clampView])

  // ── Tick marks ────────────────────────────────────────────────────────────
  const ticks = useMemo(() => {
    const first = Math.ceil(viewStart / TICK_INTERVAL_MS) * TICK_INTERVAL_MS
    const marks: number[] = []
    for (let t = first; t <= viewStart + VIEW_MS; t += TICK_INTERVAL_MS) marks.push(t)
    return marks
  }, [viewStart])

  // ── Segment positions ─────────────────────────────────────────────────────
  const visibleSegs = useMemo(() => {
    const viewEnd = viewStart + VIEW_MS
    return segments.filter(s => {
      const s0 = new Date(s.started_at).getTime()
      const s1 = new Date(s.ended_at).getTime()
      return s1 > viewStart && s0 < viewEnd
    }).map(s => {
      const s0   = new Date(s.started_at).getTime()
      const s1   = new Date(s.ended_at).getTime()
      const left = Math.max(0, (s0 - viewStart) / VIEW_MS * 100)
      const right= Math.min(100, (s1 - viewStart) / VIEW_MS * 100)
      return { key: s.id, left, width: right - left, seg: s }
    })
  }, [segments, viewStart])

  const playheadPct = useMemo(() => {
    const pct = (currentTime.getTime() - viewStart) / VIEW_MS * 100
    return pct >= 0 && pct <= 100 ? pct : null
  }, [currentTime, viewStart])

  const today = isoDate(new Date())
  const yesterday = isoDate(new Date(Date.now() - 86400_000))
  const prevDay = isoDate(new Date(new Date(date + 'T12:00:00').getTime() - 86400_000))
  const nextDay = isoDate(new Date(new Date(date + 'T12:00:00').getTime() + 86400_000))

  return (
    <div className="select-none" style={{ userSelect: 'none' }}>
      {/* Date nav */}
      {onDateChange && (
        <div className="flex items-center gap-2 mb-2">
          <button
            className="w-6 h-6 flex items-center justify-center rounded text-t3 hover:text-t1 transition"
            onClick={() => onDateChange(prevDay)}
          >
            <ChevronLeft size={14} />
          </button>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <span className="text-xs text-t2 tabular-nums">
              {date === today ? 'Hoje' : date === yesterday ? 'Ontem' : date}
            </span>
            <input
              type="date"
              className="sr-only"
              value={date}
              max={today}
              onChange={e => e.target.value && onDateChange(e.target.value)}
            />
          </label>
          <button
            className="w-6 h-6 flex items-center justify-center rounded text-t3 hover:text-t1 transition disabled:opacity-30"
            onClick={() => onDateChange(nextDay)}
            disabled={date >= today}
          >
            <ChevronRight size={14} />
          </button>
          <span className="ml-auto text-[10px] text-t3 tabular-nums">
            {segments.length} segmento{segments.length !== 1 ? 's' : ''}
          </span>
        </div>
      )}

      {/* Track row: arrow | bar | arrow */}
      <div className="flex items-center gap-1">
        <button
          className="w-7 h-7 shrink-0 flex items-center justify-center rounded text-t3 hover:text-t1 hover:bg-elevated transition"
          onClick={() => pan(-1)}
        >
          <ChevronLeft size={16} />
        </button>

        {/* The track */}
        <div className="relative flex-1 overflow-hidden" style={{ height: 48 }}>
          {/* Rail */}
          <div
            ref={trackRef}
            className="absolute inset-x-0"
            style={{ top: 6, height: 18, background: 'var(--elevated)', cursor: 'col-resize' }}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={e => { if (dragRef.current.dragging) onMouseUp(e) }}
          >
            {/* Segment fills */}
            {visibleSegs.map(({ key, left, width }) => (
              <div
                key={key}
                className="absolute top-0 h-full"
                style={{
                  left:       `${left}%`,
                  width:      `${Math.max(0.3, width)}%`,
                  background: '#14b8a6',
                  opacity:    0.9,
                }}
              />
            ))}

            {/* Playhead */}
            {playheadPct !== null && (
              <div
                className="absolute top-0 bottom-0 pointer-events-none"
                style={{ left: `${playheadPct}%`, width: 2, background: '#ef4444', zIndex: 10 }}
              >
                {/* small triangle at top */}
                <div
                  style={{
                    position: 'absolute',
                    top: -5,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    width: 0, height: 0,
                    borderLeft: '4px solid transparent',
                    borderRight: '4px solid transparent',
                    borderTop: '5px solid #ef4444',
                  }}
                />
              </div>
            )}
          </div>

          {/* Time labels */}
          <div className="absolute inset-x-0" style={{ top: 26 }}>
            {ticks.map(t => {
              const pct = (t - viewStart) / VIEW_MS * 100
              const isHour = new Date(t).getMinutes() === 0
              return (
                <div
                  key={t}
                  className="absolute flex flex-col items-center pointer-events-none"
                  style={{ left: `${pct}%`, top: 0 }}
                >
                  <div
                    style={{
                      width: 1,
                      height: isHour ? 5 : 3,
                      background: isHour ? 'var(--text-3)' : 'var(--border)',
                    }}
                  />
                  <span
                    className="-translate-x-1/2 tabular-nums"
                    style={{
                      fontSize: 9,
                      color: isHour ? 'var(--text-2)' : 'var(--text-3)',
                      fontWeight: isHour ? 500 : 400,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {hhmm(t)}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        <button
          className="w-7 h-7 shrink-0 flex items-center justify-center rounded text-t3 hover:text-t1 hover:bg-elevated transition"
          onClick={() => pan(1)}
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  )
}

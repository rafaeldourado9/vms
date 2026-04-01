import { useRef, useCallback } from 'react'

interface Segment {
  started_at: string
  ended_at: string
}

interface TimelineBarProps {
  segments: Segment[]
  date: Date
  selectedRange?: [Date, Date]
  onRangeChange?: (range: [Date, Date]) => void
}

const HOUR_LABELS = Array.from({ length: 25 }, (_, i) => i)

function toFraction(date: Date, dayStart: Date): number {
  const total = 24 * 60 * 60 * 1000
  return Math.max(0, Math.min(1, (date.getTime() - dayStart.getTime()) / total))
}

function getDayStart(date: Date): Date {
  const d = new Date(date)
  d.setHours(0, 0, 0, 0)
  return d
}

export function TimelineBar({ segments, date, selectedRange, onRangeChange }: TimelineBarProps) {
  const barRef = useRef<HTMLDivElement>(null)
  const dragRef = useRef<'left' | 'right' | 'center' | null>(null)
  const dragStartX = useRef(0)
  const dragStartRange = useRef<[Date, Date] | null>(null)

  const dayStart = getDayStart(date)

  const fractionToDate = useCallback((fraction: number): Date => {
    const ms = fraction * 24 * 60 * 60 * 1000
    return new Date(dayStart.getTime() + ms)
  }, [dayStart])

  const getBarFraction = useCallback((clientX: number): number => {
    if (!barRef.current) return 0
    const rect = barRef.current.getBoundingClientRect()
    return Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
  }, [])

  const handleBarClick = useCallback((e: React.MouseEvent) => {
    if (!onRangeChange || dragRef.current) return
    const fraction = getBarFraction(e.clientX)
    const center = fractionToDate(fraction)
    const halfHour = 30 * 60 * 1000
    onRangeChange([new Date(center.getTime() - halfHour), new Date(center.getTime() + halfHour)])
  }, [onRangeChange, getBarFraction, fractionToDate])

  const handleDragStart = useCallback((handle: 'left' | 'right' | 'center', e: React.MouseEvent) => {
    e.stopPropagation()
    if (!selectedRange) return
    dragRef.current = handle
    dragStartX.current = e.clientX
    dragStartRange.current = [new Date(selectedRange[0]), new Date(selectedRange[1])]

    const onMouseMove = (ev: MouseEvent) => {
      if (!dragRef.current || !dragStartRange.current || !barRef.current || !onRangeChange) return
      const rect = barRef.current.getBoundingClientRect()
      const deltaPx = ev.clientX - dragStartX.current
      const deltaMs = (deltaPx / rect.width) * 24 * 60 * 60 * 1000
      const [s, e] = dragStartRange.current

      if (dragRef.current === 'left') {
        const newStart = new Date(Math.min(s.getTime() + deltaMs, e.getTime() - 60000))
        onRangeChange([newStart, e])
      } else if (dragRef.current === 'right') {
        const newEnd = new Date(Math.max(e.getTime() + deltaMs, s.getTime() + 60000))
        onRangeChange([s, newEnd])
      } else {
        onRangeChange([new Date(s.getTime() + deltaMs), new Date(e.getTime() + deltaMs)])
      }
    }

    const onMouseUp = () => {
      dragRef.current = null
      dragStartRange.current = null
      window.removeEventListener('mousemove', onMouseMove)
      window.removeEventListener('mouseup', onMouseUp)
    }

    window.addEventListener('mousemove', onMouseMove)
    window.addEventListener('mouseup', onMouseUp)
  }, [selectedRange, onRangeChange])

  const rangeLeft   = selectedRange ? toFraction(selectedRange[0], dayStart) : null
  const rangeRight  = selectedRange ? toFraction(selectedRange[1], dayStart) : null
  const rangeWidth  = rangeLeft !== null && rangeRight !== null ? rangeRight - rangeLeft : null

  return (
    <div className="select-none">
      {/* Hour labels */}
      <div className="relative mb-1 flex">
        {HOUR_LABELS.filter((h) => h % 3 === 0).map((h) => (
          <span
            key={h}
            className="absolute text-[10px] text-t3"
            style={{ left: `${(h / 24) * 100}%`, transform: 'translateX(-50%)' }}
          >
            {h.toString().padStart(2, '0')}h
          </span>
        ))}
      </div>

      {/* Bar */}
      <div
        ref={barRef}
        className="relative h-7 rounded-lg overflow-hidden cursor-pointer"
        style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
        onClick={handleBarClick}
      >
        {/* Segments */}
        {segments.map((seg, idx) => {
          const start = toFraction(new Date(seg.started_at), dayStart)
          const end   = toFraction(new Date(seg.ended_at), dayStart)
          return (
            <div
              key={idx}
              className="absolute top-0 h-full opacity-70"
              style={{
                left:    `${start * 100}%`,
                width:   `${(end - start) * 100}%`,
                background: 'var(--accent)',
              }}
            />
          )
        })}

        {/* Selected range overlay */}
        {rangeLeft !== null && rangeWidth !== null && (
          <div
            className="absolute top-0 h-full"
            style={{
              left:    `${rangeLeft * 100}%`,
              width:   `${rangeWidth * 100}%`,
              background: '#F59E0B33',
              border: '1px solid #F59E0B',
              boxSizing: 'border-box',
            }}
            onMouseDown={(e) => handleDragStart('center', e)}
          >
            {/* Left handle */}
            <div
              className="absolute left-0 top-0 h-full w-2 cursor-ew-resize"
              style={{ background: '#F59E0B', opacity: 0.8 }}
              onMouseDown={(e) => handleDragStart('left', e)}
            />
            {/* Right handle */}
            <div
              className="absolute right-0 top-0 h-full w-2 cursor-ew-resize"
              style={{ background: '#F59E0B', opacity: 0.8 }}
              onMouseDown={(e) => handleDragStart('right', e)}
            />
          </div>
        )}
      </div>

      {/* Selected range label */}
      {selectedRange && (
        <div className="mt-1 flex items-center gap-2 text-[10px] text-t3">
          <span style={{ color: '#F59E0B' }}>
            {selectedRange[0].toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
            {' — '}
            {selectedRange[1].toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      )}
    </div>
  )
}

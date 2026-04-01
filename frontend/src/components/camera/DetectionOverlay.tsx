import { clsx } from 'clsx'

interface Detection {
  bbox: [number, number, number, number]  // x, y, w, h normalized 0.0–1.0
  label: string
  confidence: number
}

interface DetectionOverlayProps {
  detections: Detection[]
  className?: string
}

const LABEL_COLORS: Record<string, string> = {
  person:    '#3B82F6',
  car:       '#22C55E',
  truck:     '#F59E0B',
  motorcycle:'#8B5CF6',
  plate:     '#EF4444',
  face:      '#EC4899',
  weapon:    '#DC2626',
}

function colorForLabel(label: string): string {
  const key = label.toLowerCase()
  return LABEL_COLORS[key] ?? '#3B82F6'
}

export function DetectionOverlay({ detections, className }: DetectionOverlayProps) {
  if (detections.length === 0) return null

  return (
    <svg
      className={clsx('absolute inset-0 w-full h-full pointer-events-none', className)}
      viewBox="0 0 1 1"
      preserveAspectRatio="none"
    >
      {detections.map((det, idx) => {
        const [x, y, w, h] = det.bbox
        const color = colorForLabel(det.label)
        const labelText = `${det.label} ${Math.round(det.confidence * 100)}%`

        return (
          <g key={idx}>
            <rect
              x={x}
              y={y}
              width={w}
              height={h}
              fill="none"
              stroke={color}
              strokeWidth="0.003"
              opacity={0.9}
            />
            {/* Label background */}
            <rect
              x={x}
              y={Math.max(0, y - 0.035)}
              width={Math.min(1 - x, labelText.length * 0.012 + 0.01)}
              height={0.032}
              fill={color}
              opacity={0.85}
            />
            <text
              x={x + 0.005}
              y={Math.max(0.028, y - 0.008)}
              fontSize="0.025"
              fill="white"
              fontFamily="monospace"
              style={{ userSelect: 'none' }}
            >
              {labelText}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

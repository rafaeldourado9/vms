import { useState, useCallback, useRef } from 'react'

type Point = [number, number]

interface UseROIEditorOptions {
  onPolygonComplete?: (points: Point[]) => void
}

interface UseROIEditorReturn {
  drawing: boolean
  currentPoints: Point[]
  canvasRef: React.RefObject<HTMLDivElement>
  startDrawing: () => void
  cancelDrawing: () => void
  handleCanvasClick: (e: React.MouseEvent) => void
  handleDoubleClick: (e: React.MouseEvent) => void
  clearPoints: () => void
}

/**
 * Lógica de desenho e edição de polígonos ROI sobre um canvas.
 * Coordenadas normalizadas 0.0–1.0 relativas ao elemento canvas.
 */
export function useROIEditor({ onPolygonComplete }: UseROIEditorOptions = {}): UseROIEditorReturn {
  const canvasRef    = useRef<HTMLDivElement>(null!)
  const [drawing, setDrawing]         = useState(false)
  const [currentPoints, setPoints]    = useState<Point[]>([])

  const getRelativeCoords = (e: React.MouseEvent): Point | null => {
    if (!canvasRef.current) return null
    const rect = canvasRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width
    const y = (e.clientY - rect.top)  / rect.height
    return [parseFloat(x.toFixed(4)), parseFloat(y.toFixed(4))]
  }

  const startDrawing = useCallback(() => {
    setDrawing(true)
    setPoints([])
  }, [])

  const cancelDrawing = useCallback(() => {
    setDrawing(false)
    setPoints([])
  }, [])

  const handleCanvasClick = useCallback((e: React.MouseEvent) => {
    if (!drawing) return
    const pt = getRelativeCoords(e)
    if (!pt) return
    setPoints((prev) => [...prev, pt])
  }, [drawing])

  const handleDoubleClick = useCallback((e: React.MouseEvent) => {
    if (!drawing || currentPoints.length < 3) return
    e.preventDefault()
    onPolygonComplete?.(currentPoints)
    setPoints([])
    setDrawing(false)
  }, [drawing, currentPoints, onPolygonComplete])

  const clearPoints = useCallback(() => setPoints([]), [])

  return {
    drawing,
    currentPoints,
    canvasRef,
    startDrawing,
    cancelDrawing,
    handleCanvasClick,
    handleDoubleClick,
    clearPoints,
  }
}

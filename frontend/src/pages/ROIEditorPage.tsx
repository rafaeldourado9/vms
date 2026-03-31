import { useEffect, useRef, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Plus, Trash2, Save, X, Eye, EyeOff, MousePointer } from 'lucide-react'
import { clsx } from 'clsx'
import { camerasService } from '@/services/cameras'
import { analyticsService } from '@/services/analytics'
import { PageSpinner } from '@/components/ui/Spinner'
import { Modal } from '@/components/ui/Modal'
import toast from 'react-hot-toast'
import type { Camera, ROI, ROIType } from '@/types'

const ROI_TYPE_OPTIONS: { value: ROIType; label: string; color: string }[] = [
  { value: 'intrusion',        label: 'Intrusão',             color: '#EF4444' },
  { value: 'people_count',     label: 'Contagem Pessoas',     color: '#8B5CF6' },
  { value: 'vehicle_count',    label: 'Contagem Veículos',    color: '#F59E0B' },
  { value: 'lpr_parking',      label: 'ALPR / Estacionamento', color: '#22C55E' },
  { value: 'weapon_detection', label: 'Detecção de Arma',     color: '#EC4899' },
  { value: 'face_recognition', label: 'Reconhecimento Facial', color: '#A78BFA' },
  { value: 'vehicle_dwell',    label: 'Permanência Veicular', color: '#06B6D4' },
]

const ROI_COLOR = ROI_TYPE_OPTIONS.reduce<Record<string, string>>((acc, t) => {
  acc[t.value] = t.color; return acc
}, {})

type DrawingPoint = [number, number]

export function ROIEditorPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const canvasRef    = useRef<HTMLDivElement>(null)
  const imgRef       = useRef<HTMLImageElement>(null)

  const [camera, setCamera]         = useState<Camera | null>(null)
  const [rois, setRois]             = useState<ROI[]>([])
  const [loading, setLoading]       = useState(true)
  const [snapshotUrl, setSnapshot]  = useState('')
  const [, setImgSize]       = useState({ w: 1280, h: 720 })

  // Drawing state
  const [drawing, setDrawing]       = useState(false)
  const [currentPts, setCurrentPts] = useState<DrawingPoint[]>([])

  // New ROI form
  const [showForm, setShowForm]     = useState(false)
  const [roiName, setRoiName]       = useState('')
  const [roiType, setRoiType]       = useState<ROIType>('intrusion')
  const [pendingPts, setPendingPts] = useState<DrawingPoint[]>([])
  const [saving, setSaving]         = useState(false)

  // Visibility
  const [hidden, setHidden]         = useState<Set<string>>(new Set())
  const [selectedRoi, setSelectedRoi] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    Promise.all([
      camerasService.get(id),
      analyticsService.listROIs(id),
    ]).then(([cam, camRois]) => {
      setCamera(cam)
      setRois(camRois)
      setSnapshot(`/api/v1/cameras/${id}/snapshot`)
    }).finally(() => setLoading(false))
  }, [id])

  const getRelativeCoords = (e: React.MouseEvent): DrawingPoint | null => {
    if (!canvasRef.current) return null
    const rect = canvasRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width
    const y = (e.clientY - rect.top)  / rect.height
    return [parseFloat(x.toFixed(4)), parseFloat(y.toFixed(4))]
  }

  const handleCanvasClick = useCallback((e: React.MouseEvent) => {
    if (!drawing) return
    const pt = getRelativeCoords(e)
    if (!pt) return
    setCurrentPts((prev) => [...prev, pt])
  }, [drawing])

  const handleDoubleClick = useCallback((e: React.MouseEvent) => {
    if (!drawing || currentPts.length < 3) return
    e.preventDefault()
    setPendingPts(currentPts)
    setCurrentPts([])
    setDrawing(false)
    setShowForm(true)
  }, [drawing, currentPts])

  const handleSaveROI = async () => {
    if (!id || !roiName || pendingPts.length < 3) return
    setSaving(true)
    try {
      const newROI = await analyticsService.createROI({
        camera_id:      id,
        name:           roiName,
        ia_type:        roiType,
        polygon_points: pendingPts,
      })
      setRois((prev) => [...prev, newROI])
      setShowForm(false)
      setRoiName('')
      setPendingPts([])
      toast.success('ROI criada')
    } catch { toast.error('Erro ao criar ROI') } finally {
      setSaving(false)
    }
  }

  const handleDeleteROI = async (roi: ROI) => {
    if (!confirm(`Remover ROI "${roi.name}"?`)) return
    try {
      await analyticsService.deleteROI(roi.id)
      setRois((prev) => prev.filter((r) => r.id !== roi.id))
      toast.success('ROI removida')
    } catch { toast.error('Erro ao remover ROI') }
  }

  const toggleHide = (roiId: string) => {
    setHidden((prev) => {
      const next = new Set(prev)
      next.has(roiId) ? next.delete(roiId) : next.add(roiId)
      return next
    })
  }

  if (loading) return <PageSpinner />
  if (!camera) return <div className="text-t3 text-center py-16">Câmera não encontrada</div>

  return (
    <div className="flex h-full gap-4 animate-fade-in">
      {/* Canvas area */}
      <div className="flex-1 flex flex-col gap-3 min-w-0">
        {/* Toolbar */}
        <div className="flex items-center gap-3 shrink-0">
          <button className="btn btn-ghost w-8 h-8 p-0" onClick={() => navigate(`/cameras/${id}`)}>
            <ArrowLeft size={18} />
          </button>
          <p className="text-sm font-semibold text-t1">{camera.name} — Editor de ROI</p>
          <div className="ml-auto flex items-center gap-2">
            <button
              className={clsx('btn gap-2', drawing ? 'btn-danger' : 'btn-primary')}
              onClick={() => { setDrawing((d) => !d); setCurrentPts([]) }}
            >
              {drawing ? <><X size={15} />Cancelar</> : <><Plus size={15} />Nova ROI</>}
            </button>
          </div>
        </div>

        {drawing && (
          <div
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs"
            style={{ background: 'rgba(59,130,246,0.1)', border: '1px solid rgba(59,130,246,0.3)', color: '#93C5FD' }}
          >
            <MousePointer size={14} />
            Clique para adicionar pontos ao polígono. Dê duplo-clique para finalizar (mín. 3 pontos).
            {currentPts.length > 0 && <span className="ml-auto">{currentPts.length} pontos</span>}
          </div>
        )}

        {/* Canvas */}
        <div
          ref={canvasRef}
          className={clsx(
            'relative flex-1 rounded-xl overflow-hidden bg-black select-none min-h-[300px]',
            drawing ? 'cursor-crosshair' : 'cursor-default',
          )}
          onClick={handleCanvasClick}
          onDoubleClick={handleDoubleClick}
        >
          <img
            ref={imgRef}
            src={snapshotUrl}
            alt={camera.name}
            className="w-full h-full object-contain"
            onLoad={(e) => {
              const img = e.currentTarget
              setImgSize({ w: img.naturalWidth, h: img.naturalHeight })
            }}
            onError={() => setSnapshot('')}
          />

          {/* SVG overlay */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            {/* Existing ROIs */}
            {rois.filter((r) => !hidden.has(r.id)).map((roi) => {
              const color = ROI_COLOR[roi.ia_type] ?? '#3B82F6'
              const pts   = roi.polygon_points
              if (!pts || pts.length < 2) return null
              const svgPts = pts.map(([x, y]) => `${(x * 100).toFixed(2)}% ${(y * 100).toFixed(2)}%`).join(' ')
              return (
                <g key={roi.id} onClick={() => setSelectedRoi(roi.id === selectedRoi ? null : roi.id)}>
                  <polygon
                    points={svgPts}
                    fill={color + '30'}
                    stroke={color}
                    strokeWidth={selectedRoi === roi.id ? 2.5 : 1.5}
                    className="cursor-pointer"
                    style={{ pointerEvents: 'all' }}
                  />
                  {/* Label */}
                  {pts.length > 0 && (
                    <text
                      x={`${(pts[0][0] * 100).toFixed(1)}%`}
                      y={`${(pts[0][1] * 100 - 1).toFixed(1)}%`}
                      fill={color}
                      fontSize="11"
                      fontWeight="600"
                      style={{ pointerEvents: 'none', userSelect: 'none' }}
                    >
                      {roi.name}
                    </text>
                  )}
                </g>
              )
            })}

            {/* Drawing in progress */}
            {currentPts.length > 0 && (
              <>
                {currentPts.length > 1 && (
                  <polyline
                    points={currentPts.map(([x, y]) => `${(x * 100).toFixed(2)}% ${(y * 100).toFixed(2)}%`).join(' ')}
                    fill="none"
                    stroke="#3B82F6"
                    strokeWidth="2"
                    strokeDasharray="5 3"
                  />
                )}
                {currentPts.map(([x, y], i) => (
                  <circle
                    key={i}
                    cx={`${(x * 100).toFixed(2)}%`}
                    cy={`${(y * 100).toFixed(2)}%`}
                    r="5"
                    fill="#3B82F6"
                    stroke="white"
                    strokeWidth="1.5"
                  />
                ))}
              </>
            )}
          </svg>
        </div>
      </div>

      {/* Sidebar */}
      <div className="w-64 shrink-0 flex flex-col gap-3">
        <p className="text-xs font-semibold text-t2 uppercase tracking-wide">ROIs ({rois.length})</p>
        <div className="space-y-2 flex-1 overflow-y-auto">
          {rois.map((roi) => {
            const color = ROI_COLOR[roi.ia_type] ?? '#3B82F6'
            return (
              <div
                key={roi.id}
                className={clsx(
                  'card p-3 cursor-pointer transition-all',
                  selectedRoi === roi.id ? 'border-accent' : '',
                )}
                style={selectedRoi === roi.id ? { borderColor: color } : {}}
                onClick={() => setSelectedRoi(roi.id === selectedRoi ? null : roi.id)}
              >
                <div className="flex items-start gap-2">
                  <div className="w-3 h-3 rounded-sm mt-0.5 shrink-0" style={{ background: color }} />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-t1 truncate">{roi.name}</p>
                    <p className="text-xs text-t3">{ROI_TYPE_OPTIONS.find((t) => t.value === roi.ia_type)?.label}</p>
                    <p className="text-xs text-t3">{roi.polygon_points?.length} pontos</p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      className="btn btn-ghost w-6 h-6 p-0 rounded"
                      onClick={(e) => { e.stopPropagation(); toggleHide(roi.id) }}
                      title={hidden.has(roi.id) ? 'Mostrar' : 'Ocultar'}
                    >
                      {hidden.has(roi.id) ? <EyeOff size={12} /> : <Eye size={12} />}
                    </button>
                    <button
                      className="btn btn-ghost w-6 h-6 p-0 rounded text-danger"
                      onClick={(e) => { e.stopPropagation(); handleDeleteROI(roi) }}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
          {rois.length === 0 && (
            <div className="text-center py-6">
              <p className="text-xs text-t3">Nenhuma ROI</p>
              <p className="text-xs text-t3 mt-1">Clique em "Nova ROI" para começar</p>
            </div>
          )}
        </div>
      </div>

      {/* Save ROI Modal */}
      <Modal
        open={showForm}
        onClose={() => { setShowForm(false); setPendingPts([]) }}
        title="Configurar Nova ROI"
        size="sm"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => { setShowForm(false); setPendingPts([]) }}>
              Cancelar
            </button>
            <button
              className="btn btn-primary"
              onClick={handleSaveROI}
              disabled={saving || !roiName}
            >
              <Save size={14} />{saving ? 'Salvando...' : 'Salvar ROI'}
            </button>
          </>
        }
      >
        <div className="space-y-4">
          <div>
            <label className="label">Nome da ROI *</label>
            <input
              className="input"
              placeholder="Ex: Zona de Intrusão A"
              value={roiName}
              onChange={(e) => setRoiName(e.target.value)}
              autoFocus
            />
          </div>
          <div>
            <label className="label">Tipo de Analítico</label>
            <div className="space-y-1.5">
              {ROI_TYPE_OPTIONS.map((t) => (
                <button
                  key={t.value}
                  onClick={() => setRoiType(t.value)}
                  className={clsx(
                    'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-xs font-medium border transition',
                    roiType === t.value ? 'text-white' : 'text-t2 hover:text-t1',
                  )}
                  style={
                    roiType === t.value
                      ? { background: t.color + '30', borderColor: t.color, color: t.color }
                      : { borderColor: 'var(--border)' }
                  }
                >
                  <span className="w-3 h-3 rounded-sm shrink-0" style={{ background: t.color }} />
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <p className="text-xs text-t3">{pendingPts.length} pontos definidos</p>
        </div>
      </Modal>
    </div>
  )
}

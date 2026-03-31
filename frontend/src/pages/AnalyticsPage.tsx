import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BarChart3, Map, Camera, TrendingUp } from 'lucide-react'
import { analyticsService } from '@/services/analytics'
import { camerasService } from '@/services/cameras'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import type { ROI, Camera as CameraType, AnalyticsSummary } from '@/types'

const ROI_TYPE_LABELS: Record<string, string> = {
  intrusion:        'Intrusão',
  people_count:     'Contagem Pessoas',
  vehicle_count:    'Contagem Veículos',
  lpr_parking:      'ALPR Estacionamento',
  weapon_detection: 'Detecção Arma',
  face_recognition: 'Reconhecimento Facial',
  vehicle_dwell:    'Permanência Veicular',
}

export function AnalyticsPage() {
  const navigate = useNavigate()
  const [rois, setRois]         = useState<ROI[]>([])
  const [cameras, setCameras]   = useState<CameraType[]>([])
  const [summary, setSummary]   = useState<AnalyticsSummary | null>(null)
  const [loading, setLoading]   = useState(true)

  useEffect(() => {
    Promise.all([
      analyticsService.listROIs(),
      camerasService.list({ page_size: 200 }),
      analyticsService.summary({ hours: 24 }).catch(() => null),
    ]).then(([r, c, s]) => {
      setRois(r)
      setCameras(c)
      setSummary(s)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <PageSpinner />

  const roisByCamera: Record<string, ROI[]> = {}
  rois.forEach((roi) => {
    if (!roisByCamera[roi.camera_id]) roisByCamera[roi.camera_id] = []
    roisByCamera[roi.camera_id].push(roi)
  })

  const totalEvents   = summary?.total_events ?? 0
  const activeROIs    = rois.filter((r) => r.is_active).length
  const uniqueTypes   = new Set(rois.map((r) => r.ia_type)).size

  const statCards = [
    { label: 'Eventos (24h)',   value: totalEvents,         icon: TrendingUp, color: '#3B82F6' },
    { label: 'ROIs Ativas',     value: activeROIs,          icon: Map,        color: '#22C55E' },
    { label: 'Total de ROIs',   value: rois.length,         icon: BarChart3,  color: '#F59E0B' },
    { label: 'Tipos de Plugin', value: uniqueTypes,         icon: Camera,     color: '#8B5CF6' },
  ]

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {statCards.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card px-4 py-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-t2 font-medium">{label}</p>
              <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: color + '18' }}>
                <Icon size={16} style={{ color }} />
              </div>
            </div>
            <p className="text-2xl font-bold text-t1">{value}</p>
          </div>
        ))}
      </div>

      {/* Events by type */}
      {summary && Object.keys(summary.by_type).length > 0 && (
        <div className="card p-4">
          <p className="text-sm font-semibold text-t1 mb-4">Eventos por Tipo (24h)</p>
          <div className="space-y-3">
            {Object.entries(summary.by_type)
              .sort(([, a], [, b]) => b - a)
              .map(([type, count]) => {
                const maxCount = Math.max(...Object.values(summary.by_type))
                return (
                  <div key={type} className="flex items-center gap-3">
                    <p className="text-xs text-t2 w-40 truncate">{ROI_TYPE_LABELS[type] ?? type}</p>
                    <div className="flex-1 h-2 rounded-full overflow-hidden" style={{ background: 'var(--elevated)' }}>
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          background: 'var(--accent)',
                          width: `${(count / maxCount) * 100}%`,
                        }}
                      />
                    </div>
                    <span className="text-xs font-semibold text-t1 w-10 text-right">{count}</span>
                  </div>
                )
              })}
          </div>
        </div>
      )}

      {/* ROIs by camera */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-t1">ROIs por Câmera</p>
        </div>

        {Object.keys(roisByCamera).length === 0 ? (
          <div className="card p-16 text-center">
            <BarChart3 size={32} className="text-t3 mx-auto mb-3" />
            <p className="text-t3 text-sm">Nenhuma ROI configurada</p>
            <p className="text-t3 text-xs mt-1">Acesse uma câmera e configure ROIs para habilitar analytics</p>
          </div>
        ) : (
          Object.entries(roisByCamera).map(([cameraId, camRois]) => {
            const camera = cameras.find((c) => c.id === cameraId)
            return (
              <div key={cameraId} className="card p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <p className="text-sm font-semibold text-t1">{camera?.name ?? cameraId.slice(0, 8)}</p>
                    <p className="text-xs text-t3">{camRois.length} ROIs · {camRois.filter((r) => r.is_active).length} ativas</p>
                  </div>
                  <button
                    className="btn btn-ghost text-xs gap-1"
                    onClick={() => navigate(`/cameras/${cameraId}/roi`)}
                  >
                    <Map size={14} />Editar ROIs
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {camRois.map((roi) => (
                    <div
                      key={roi.id}
                      className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs"
                      style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
                    >
                      <div className={`w-1.5 h-1.5 rounded-full ${roi.is_active ? 'bg-green-500' : 'bg-zinc-600'}`} />
                      <span className="text-t1">{roi.name}</span>
                      <Badge variant="info" className="text-xs">{ROI_TYPE_LABELS[roi.ia_type] ?? roi.ia_type}</Badge>
                    </div>
                  ))}
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

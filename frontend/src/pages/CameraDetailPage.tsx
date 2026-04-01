import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Settings, Map, Wifi, Edit2, Save, X, Film, ShieldAlert, Camera as CameraIcon } from 'lucide-react'
import { clsx } from 'clsx'
import { format } from 'date-fns'
import { camerasService } from '@/services/cameras'
import { analyticsService } from '@/services/analytics'
import { eventsService } from '@/services/events'
import { recordingsService } from '@/services/recordings'
import { VideoPlayer } from '@/components/camera/VideoPlayer'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { usePermission } from '@/hooks/usePermission'
import toast from 'react-hot-toast'
import type { Camera, ROI, VmsEvent, Clip } from '@/types'

type Tab = 'live' | 'info' | 'rois' | 'events' | 'clips'

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'live',   label: 'Ao Vivo',     icon: Wifi },
  { id: 'info',   label: 'Informações', icon: Settings },
  { id: 'rois',   label: 'ROIs',        icon: Map },
  { id: 'events', label: 'Eventos',     icon: ShieldAlert },
  { id: 'clips',  label: 'Clips',       icon: Film },
]

const EVENT_LABELS: Record<string, string> = {
  alpr: 'ALPR', intrusion: 'Intrusão', people_count: 'Pessoas',
  vehicle_count: 'Veículos', lpr_parking: 'Estacionamento',
  weapon_detection: 'Arma', face_recognition: 'Facial', vehicle_dwell: 'Dwell',
}

export function CameraDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { isAdmin } = usePermission()

  const [tab, setTab]           = useState<Tab>('live')
  const [camera, setCamera]     = useState<Camera | null>(null)
  const [streamUrl, setStream]  = useState('')
  const [rois, setRois]         = useState<ROI[]>([])
  const [events, setEvents]     = useState<VmsEvent[]>([])
  const [clips, setClips]       = useState<Clip[]>([])
  const [loading, setLoading]   = useState(true)
  const [editing, setEditing]     = useState(false)
  const [editForm, setEditForm]   = useState<Partial<Camera>>({})
  const [snapshotOpen, setSnapshotOpen] = useState(false)
  const [snapshotUrl, setSnapshotUrl]   = useState('')
  const [snapshotLoading, setSnapshotLoading] = useState(false)

  useEffect(() => {
    if (!id) return
    Promise.all([
      camerasService.get(id),
      camerasService.streamUrls(id).catch(() => ({ hls_url: '' })),
    ]).then(([cam, urls]) => {
      setCamera(cam)
      setEditForm(cam)
      setStream(urls.hls_url ?? '')
    }).finally(() => setLoading(false))
  }, [id])

  useEffect(() => {
    if (!id || tab === 'live' || tab === 'info') return
    if (tab === 'rois') {
      analyticsService.listROIs(id).then(setRois).catch(() => setRois([]))
    }
    if (tab === 'events') {
      eventsService.list({ camera_id: id, page_size: 20 }).then((r) => setEvents(r.items ?? []))
    }
    if (tab === 'clips') {
      recordingsService.listClips({ camera_id: id }).then((r) => setClips(r.items ?? []))
    }
  }, [id, tab])

  const handleSave = async () => {
    if (!id || !camera) return
    try {
      const updated = await camerasService.update(id, {
        name:          editForm.name,
        location:      editForm.location ?? undefined,
        retention_days: editForm.retention_days,
      })
      setCamera(updated)
      setEditing(false)
      toast.success('Câmera atualizada')
    } catch { toast.error('Erro ao salvar') }
  }

  const openSnapshot = async () => {
    if (!id) return
    setSnapshotLoading(true)
    setSnapshotOpen(true)
    try {
      const { snapshot_url } = await camerasService.snapshot(id)
      setSnapshotUrl(snapshot_url)
    } catch {
      toast.error('Erro ao capturar snapshot')
      setSnapshotOpen(false)
    } finally {
      setSnapshotLoading(false)
    }
  }

  const toggleROI = async (roi: ROI) => {
    try {
      const updated = await analyticsService.updateROI(roi.id, { is_active: !roi.is_active })
      setRois((prev) => prev.map((r) => r.id === roi.id ? updated : r))
    } catch { toast.error('Erro ao atualizar ROI') }
  }

  if (loading) return <PageSpinner />
  if (!camera) return <div className="text-t3 text-center py-16">Câmera não encontrada</div>

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button className="btn btn-ghost w-8 h-8 p-0" onClick={() => navigate('/cameras')}>
          <ArrowLeft size={18} />
        </button>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-base font-semibold text-t1 truncate">{camera.name}</p>
            <Badge variant={camera.is_online ? 'success' : 'danger'} dot>
              {camera.is_online ? 'Online' : 'Offline'}
            </Badge>
          </div>
          <p className="text-xs text-t3 truncate">{camera.location ?? '—'}</p>
        </div>
      </div>

      {/* Tabs */}
      <div
        className="flex items-center gap-1 p-1 rounded-xl w-fit"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
      >
        {TABS.map(({ id: tid, label, icon: Icon }) => (
          <button
            key={tid}
            onClick={() => setTab(tid)}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
              tab === tid ? 'text-white' : 'text-t2 hover:text-t1',
            )}
            style={tab === tid ? { background: 'var(--accent)' } : {}}
          >
            <Icon size={14} />{label}
          </button>
        ))}
      </div>

      {/* Live */}
      {tab === 'live' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <VideoPlayer src={streamUrl} name={camera.name} className="aspect-video w-full" />
          </div>
          <div className="space-y-3">
            <div className="card p-4 space-y-3">
              <p className="text-xs font-semibold text-t2 uppercase tracking-wide">Status</p>
              <div className="space-y-2">
                {[
                  { label: 'Protocolo',  value: camera.stream_protocol.replace('_', ' ').toUpperCase() },
                  { label: 'Fabricante', value: camera.manufacturer },
                  { label: 'Retenção',   value: `${camera.retention_days} dias` },
                  { label: 'Agent',      value: camera.agent_id ? camera.agent_id.slice(0, 8) + '…' : '—' },
                  { label: 'Última vez', value: camera.last_seen_at ? format(new Date(camera.last_seen_at), 'dd/MM HH:mm') : '—' },
                ].map(({ label, value }) => (
                  <div key={label} className="flex justify-between">
                    <span className="text-xs text-t3">{label}</span>
                    <span className="text-xs text-t1 font-medium">{value}</span>
                  </div>
                ))}
              </div>
            </div>
            <button
              className="btn btn-ghost w-full gap-2"
              onClick={openSnapshot}
            >
              <CameraIcon size={15} />Snapshot
            </button>
            <button
              className="btn btn-primary w-full gap-2"
              onClick={() => navigate(`/cameras/${id}/roi`)}
            >
              <Map size={15} />Editor de ROI
            </button>
          </div>
        </div>
      )}

      {/* Snapshot modal */}
      <Modal open={snapshotOpen} onClose={() => setSnapshotOpen(false)} title="Snapshot" size="lg">
        <div className="flex items-center justify-center min-h-[200px]">
          {snapshotLoading ? (
            <div className="text-t3 text-sm">Capturando snapshot…</div>
          ) : snapshotUrl ? (
            <img
              src={snapshotUrl}
              alt="Snapshot"
              className="w-full h-auto rounded-lg object-contain"
            />
          ) : (
            <div className="text-t3 text-sm">Snapshot indisponível</div>
          )}
        </div>
      </Modal>

      {/* Info */}
      {tab === 'info' && (
        <div className="card p-6 max-w-2xl">
          <div className="flex items-center justify-between mb-6">
            <p className="text-sm font-semibold text-t1">Informações da Câmera</p>
            {isAdmin && !editing && (
              <button className="btn btn-ghost gap-2 text-xs" onClick={() => setEditing(true)}>
                <Edit2 size={14} />Editar
              </button>
            )}
            {editing && (
              <div className="flex gap-2">
                <button className="btn btn-ghost text-xs gap-1" onClick={() => { setEditing(false); setEditForm(camera) }}>
                  <X size={14} />Cancelar
                </button>
                <button className="btn btn-primary text-xs gap-1" onClick={handleSave}>
                  <Save size={14} />Salvar
                </button>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { label: 'Nome',            field: 'name',           type: 'text' },
              { label: 'Localização',     field: 'location',       type: 'text' },
              { label: 'Fabricante',      field: 'manufacturer',   type: 'text' },
              { label: 'Retenção (dias)', field: 'retention_days', type: 'number' },
              { label: 'URL RTSP',        field: 'rtsp_url',       type: 'text' },
            ].map(({ label, field, type }) => (
              <div key={field}>
                <label className="label">{label}</label>
                {editing ? (
                  <input
                    className="input"
                    type={type}
                    value={(editForm as Record<string, unknown>)[field] as string ?? ''}
                    onChange={(e) => setEditForm((f) => ({
                      ...f,
                      [field]: type === 'number' ? Number(e.target.value) : e.target.value,
                    }))}
                  />
                ) : (
                  <p className="text-sm text-t1 mt-1">{(camera as unknown as Record<string, unknown>)[field] as string ?? '—'}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ROIs */}
      {tab === 'rois' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-xs text-t3">{rois.length} ROIs configuradas</p>
            <button className="btn btn-primary gap-2" onClick={() => navigate(`/cameras/${id}/roi`)}>
              <Map size={15} />Abrir Editor de ROI
            </button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {rois.map((roi) => (
              <div key={roi.id} className="card p-4 flex items-start gap-3">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-t1">{roi.name}</p>
                  <p className="text-xs text-t3">{roi.ia_type}</p>
                  <p className="text-xs text-t3">{roi.polygon_points?.length ?? 0} pontos</p>
                </div>
                <button
                  className={clsx('relative w-10 h-6 rounded-full transition-colors shrink-0')}
                  style={roi.is_active ? { background: 'var(--accent)' } : { background: 'var(--elevated)' }}
                  onClick={() => toggleROI(roi)}
                >
                  <div className={clsx(
                    'absolute top-1 w-4 h-4 rounded-full bg-white transition-transform',
                    roi.is_active ? 'translate-x-5' : 'translate-x-1',
                  )} />
                </button>
              </div>
            ))}
            {rois.length === 0 && (
              <div className="col-span-full card p-16 text-center">
                <Map size={32} className="text-t3 mx-auto mb-3" />
                <p className="text-t3 text-sm">Nenhuma ROI configurada</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Events */}
      {tab === 'events' && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left" style={{ borderColor: 'var(--border)' }}>
                {['Tipo', 'Placa', 'Data/Hora'].map((h) => (
                  <th key={h} className="px-4 py-3 text-xs font-medium text-t3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id} className="border-b hover:bg-elevated transition" style={{ borderColor: 'var(--border)' }}>
                  <td className="px-4 py-3">
                    <Badge variant="info">{EVENT_LABELS[e.event_type] ?? e.event_type}</Badge>
                  </td>
                  <td className="px-4 py-3 text-t2 text-xs font-mono">{e.plate ?? '—'}</td>
                  <td className="px-4 py-3 text-t3 text-xs">
                    {format(new Date(e.occurred_at), 'dd/MM/yy HH:mm:ss')}
                  </td>
                </tr>
              ))}
              {events.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-4 py-12 text-center text-t3 text-sm">Nenhum evento recente</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Clips */}
      {tab === 'clips' && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {clips.map((clip) => (
            <div key={clip.id} className="card overflow-hidden">
              <div className="aspect-video bg-black flex items-center justify-center">
                <Film size={24} className="text-t3" />
              </div>
              <div className="p-3">
                <p className="text-sm font-medium text-t1 truncate">{clip.name}</p>
                <p className="text-xs text-t3">{format(new Date(clip.created_at), 'dd/MM/yyyy HH:mm')}</p>
                <Badge
                  variant={clip.status === 'ready' ? 'success' : clip.status === 'error' ? 'danger' : 'warning'}
                  className="mt-2"
                >
                  {clip.status}
                </Badge>
              </div>
            </div>
          ))}
          {clips.length === 0 && (
            <div className="col-span-full card p-16 text-center">
              <Film size={32} className="text-t3 mx-auto mb-3" />
              <p className="text-t3 text-sm">Nenhum clip criado</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

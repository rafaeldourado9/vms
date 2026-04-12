import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  ArrowLeft, Settings, Wifi, Edit2, Save, X, Film, ShieldAlert,
  Camera as CameraIcon, Copy, Check, ExternalLink, Eye, EyeOff,
  Download, Radio,
} from 'lucide-react'
import { clsx } from 'clsx'
import { format } from 'date-fns'
import { camerasService } from '@/services/cameras'
import { eventsService } from '@/services/events'
import { recordingsService } from '@/services/recordings'
import { VideoPlayer } from '@/components/camera/VideoPlayer'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { usePermission } from '@/hooks/usePermission'
import type { Camera, VmsEvent, Clip } from '@/types'
import toast from 'react-hot-toast'

type Tab = 'live' | 'info' | 'events' | 'clips'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function maskRtspPassword(url: string | null | undefined): string {
  if (!url) return '—'
  return url.replace(/(rtsp?:\/\/[^:]+:)([^@]+)(@)/, '$1•••$3')
}

function parseLocation(loc: string | null | undefined): { label: string; href: string | null } {
  if (!loc) return { label: '—', href: null }
  try {
    const u = new URL(loc)
    if (u.hostname.includes('google') || u.hostname.includes('goo.gl')) {
      const m = loc.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/) ?? loc.match(/[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)/)
      if (m) return { label: `${parseFloat(m[1]).toFixed(5)}, ${parseFloat(m[2]).toFixed(5)}`, href: loc }
      return { label: 'Ver no mapa', href: loc }
    }
    return { label: u.hostname + (u.pathname !== '/' ? u.pathname : ''), href: loc }
  } catch {
    return { label: loc, href: null }
  }
}

function RtspField({ url }: { url: string | null }) {
  const [show, setShow] = useState(false)
  if (!url) return <p className="text-sm text-t1 mt-1">—</p>
  return (
    <div className="flex items-center gap-2 mt-1">
      <p className="text-sm text-t1 font-mono break-all flex-1">
        {show ? url : maskRtspPassword(url)}
      </p>
      <button
        className="btn btn-ghost w-7 h-7 p-0 shrink-0"
        onClick={() => setShow((s) => !s)}
        title={show ? 'Ocultar senha' : 'Mostrar senha'}
      >
        {show ? <EyeOff size={13} /> : <Eye size={13} />}
      </button>
    </div>
  )
}

function CopyField({ label, value, copyKey, copied, onCopy }: {
  label: string
  value: string
  copyKey: string
  copied: string | null
  onCopy: (v: string, k: string) => void
}) {
  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex items-center gap-2 mt-1">
        <code className="flex-1 text-xs font-mono rounded-lg px-3 py-2 text-t1 break-all"
          style={{ background: 'var(--elevated)' }}>
          {value}
        </code>
        <button className="btn btn-ghost w-8 h-8 p-0 shrink-0" onClick={() => onCopy(value, copyKey)}
          title="Copiar">
          {copied === copyKey
            ? <Check size={14} style={{ color: 'var(--success)' }} />
            : <Copy size={14} />}
        </button>
      </div>
    </div>
  )
}

function useServerAddress() {
  const isLocalhost = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname)
  const [tunnelUrl, setTunnelUrl] = useState<string | null>(null)
  const [, setTunnelChecked] = useState(false)

  useEffect(() => {
    if (!isLocalhost) { setTunnelChecked(true); return }

    let active = true
    let timer: ReturnType<typeof setTimeout>

    async function poll() {
      try {
        const r = await fetch('/system/server-address')
        const data: { tunnel_url: string | null } = await r.json()
        if (!active) return
        setTunnelChecked(true)
        if (data.tunnel_url) {
          setTunnelUrl(data.tunnel_url)
        } else {
          timer = setTimeout(poll, 3000)
        }
      } catch {
        if (active) timer = setTimeout(poll, 3000)
      }
    }

    poll()
    return () => { active = false; clearTimeout(timer) }
  }, [isLocalhost])

  if (!isLocalhost) {
    const port = window.location.port
    const portSuffix = port && port !== '80' && port !== '443' ? `:${port}` : ''
    return {
      ready: true,
      baseUrl: `${window.location.protocol}//${window.location.hostname}${portSuffix}`,
      host: window.location.hostname,
      port: port || '80',
      tunnelUrl: null as string | null,
    }
  }

  if (tunnelUrl) {
    const hostOnly = tunnelUrl.replace(/^https?:\/\//, '').split('/')[0].split(':')[0]
    return { ready: true, baseUrl: tunnelUrl, host: hostOnly, port: '443', tunnelUrl }
  }

  return { ready: false, baseUrl: '', host: '', port: '', tunnelUrl: null }
}

function WebhookSection({ camera }: { camera: Camera }) {
  const [copied, setCopied] = useState<string | null>(null)
  const { ready, baseUrl, host, port, tunnelUrl } = useServerAddress()
  const isLocalhost = ['localhost', '127.0.0.1', '::1'].includes(window.location.hostname)

  function copy(text: string, key: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key)
      setTimeout(() => setCopied(null), 2000)
    })
  }

  return (
    <div className="mt-6 pt-6 border-t border-border space-y-5">
      <div>
        <p className="text-sm font-semibold text-t1">Configuração de Eventos na Câmera</p>
        <p className="text-xs text-t3 mt-0.5">
          Copie os campos abaixo e cole nas configurações da câmera. Não requer autenticação.
        </p>
      </div>

      {isLocalhost && !ready && (
        <div className="rounded-xl p-3 flex items-center gap-3"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)' }}>
          <svg className="animate-spin shrink-0" width={14} height={14} viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth={2}>
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
          <p className="text-xs text-t3">Obtendo endereço do servidor…</p>
        </div>
      )}

      {ready && tunnelUrl && (
        <div className="rounded-xl p-3 space-y-1"
          style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.25)' }}>
          <p className="text-xs text-green-400 font-medium">Endereço detectado automaticamente</p>
          <p className="text-[11px] text-t3 break-all">{tunnelUrl}</p>
        </div>
      )}

      {ready && camera.manufacturer === 'intelbras' && (
        <div className="rounded-xl border p-4 space-y-3" style={{ borderColor: 'var(--border)' }}>
          <p className="text-xs font-semibold text-t2 uppercase tracking-wide">
            Intelbras — Função Push
          </p>
          <CopyField label='Campo "Cliente"' value={`${baseUrl}/intelbras_events`}
            copyKey="client" copied={copied} onCopy={copy} />
          <CopyField label='Campo "Nº dispos." — identificador desta câmera' value={camera.id}
            copyKey="devid" copied={copied} onCopy={copy} />
          <p className="text-[11px] text-t3 leading-relaxed">
            Em <strong className="text-t2">Função</strong>, marque <strong className="text-t2">Info Placa</strong>.
            Em <strong className="text-t2">Informação de upload</strong>, marque <strong className="text-t2">Nº placa</strong> e <strong className="text-t2">Confiabilidade</strong>.
          </p>
        </div>
      )}

      {ready && camera.manufacturer === 'hikvision' && (
        <div className="rounded-xl border p-4 space-y-3" style={{ borderColor: 'var(--border)' }}>
          <p className="text-xs font-semibold text-t2 uppercase tracking-wide">
            Hikvision — Servidor de Alarme
          </p>
          <CopyField label="IP de destino / Nome do anfitrião" value={host}
            copyKey="hik_host" copied={copied} onCopy={copy} />
          <CopyField label="URL" value={`/hik_pro_connect?camera_id=${camera.id}`}
            copyKey="hik_url" copied={copied} onCopy={copy} />
          <div className="grid grid-cols-2 gap-3">
            <CopyField label="Porta N.º" value={port}
              copyKey="hik_port" copied={copied} onCopy={copy} />
            <div>
              <label className="label">Tipo de protocolo</label>
              <p className="text-xs text-t1 mt-1 px-3 py-2 rounded-lg"
                style={{ background: 'var(--elevated)' }}>HTTP</p>
            </div>
          </div>
        </div>
      )}

      {ready && camera.manufacturer !== 'hikvision' && camera.manufacturer !== 'intelbras' && (
        <div className="rounded-xl border p-4 space-y-3" style={{ borderColor: 'var(--border)' }}>
          <p className="text-xs font-semibold text-t2 uppercase tracking-wide">Endpoint genérico</p>
          <CopyField label="URL completa" value={`${baseUrl}/camera_events?camera_id=${camera.id}`}
            copyKey="gen_url" copied={copied} onCopy={copy} />
        </div>
      )}
    </div>
  )
}

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'live',   label: 'Ao Vivo',     icon: Wifi },
  { id: 'info',   label: 'Informações', icon: Settings },
  { id: 'events', label: 'Eventos',     icon: ShieldAlert },
  { id: 'clips',  label: 'Clips',       icon: Film },
]

export function CameraDetailPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { isAdmin } = usePermission()

  const [tab, setTab]             = useState<Tab>('live')
  const [camera, setCamera]       = useState<Camera | null>(null)
  const [streamUrl, setStream]    = useState('')
  const [events, setEvents]       = useState<VmsEvent[]>([])
  const [clips, setClips]         = useState<Clip[]>([])
  const [loading, setLoading]     = useState(true)
  const [editing, setEditing]     = useState(false)
  const [editForm, setEditForm]   = useState<Partial<Camera>>({})
  const [snapshotOpen, setSnapshotOpen]       = useState(false)
  const [snapshotUrl, setSnapshotUrl]         = useState('')
  const [snapshotLoading, setSnapshotLoading] = useState(false)
  const [snapshotError, setSnapshotError]     = useState(false)

  // ── Camera + stream loading ───────────────────────────────────────────────
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
        name:           editForm.name,
        location:       editForm.location ?? undefined,
        retention_days: editForm.retention_days,
      })
      setCamera(updated)
      setEditing(false)
      toast.success('Câmera atualizada')
    } catch { toast.error('Erro ao salvar') }
  }

  const openSnapshot = async () => {
    if (!id) return
    setSnapshotUrl('')
    setSnapshotError(false)
    setSnapshotLoading(true)
    setSnapshotOpen(true)
    try {
      const url = await camerasService.snapshot(id)
      if (url) {
        setSnapshotUrl(url)
      } else {
        setSnapshotError(true)
      }
    } catch {
      setSnapshotError(true)
    } finally {
      setSnapshotLoading(false)
    }
  }

  const closeSnapshot = () => {
    setSnapshotOpen(false)
    setSnapshotUrl('')
    setSnapshotError(false)
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
          <p className="text-xs text-t3 truncate">{parseLocation(camera.location).label}</p>
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
        <div className="space-y-3">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Player */}
            <div className="lg:col-span-2 space-y-2">
              {/* Live badge */}
              <div className="flex items-center gap-2">
                <span
                  className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-bold"
                  style={{ background: 'rgba(239,68,68,0.12)', color: '#ef4444' }}
                >
                  <Radio size={11} className="animate-pulse" />
                  AO VIVO
                </span>
              </div>

              <VideoPlayer
                src={streamUrl || undefined}
                name={camera.name}
                offline={!camera.is_online}
                className="aspect-video w-full"
                autoPlay
              />
            </div>

            {/* Side panel */}
            <div className="space-y-3">
              <div className="card p-4 space-y-3">
                <p className="text-xs font-semibold text-t2 uppercase tracking-wide">Status</p>
                <div className="space-y-2">
                  {[
                    { label: 'Protocolo',  value: camera.stream_protocol.replace('_', ' ').toUpperCase() },
                    { label: 'Fabricante', value: camera.manufacturer },
                    { label: 'Retenção',   value: `${camera.retention_days} dias` },
                    { label: 'Última vez', value: camera.last_seen_at ? new Date(camera.last_seen_at).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—' },
                  ].map(({ label, value }) => (
                    <div key={label} className="flex justify-between">
                      <span className="text-xs text-t3">{label}</span>
                      <span className="text-xs text-t1 font-medium">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
              <button className="btn btn-ghost w-full gap-2" onClick={openSnapshot}>
                <CameraIcon size={15} />Snapshot
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Snapshot modal */}
      <Modal
        open={snapshotOpen}
        onClose={closeSnapshot}
        title={`Snapshot — ${camera.name}`}
        size="xl"
        footer={snapshotUrl && !snapshotError ? (
          <a
            href={snapshotUrl}
            download={`snapshot_${camera.name.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.jpg`}
            className="btn btn-primary gap-2 text-sm"
          >
            <Download size={14} />Salvar imagem
          </a>
        ) : undefined}
      >
        {snapshotLoading ? (
          <div className="flex items-center justify-center py-10 gap-3 text-t3">
            <div className="w-5 h-5 border-2 border-t-accent rounded-full animate-spin" />
            <span className="text-sm">Capturando snapshot…</span>
          </div>
        ) : snapshotError ? (
          <div className="flex flex-col items-center justify-center py-10 gap-3 text-t3">
            <CameraIcon size={36} className="text-t3/30" />
            <p className="text-sm font-medium">Snapshot indisponível</p>
            <p className="text-xs text-t3/60 text-center max-w-xs">
              A câmera pode estar offline ou não suportar captura de snapshot.
            </p>
          </div>
        ) : snapshotUrl ? (
          <img
            src={snapshotUrl}
            alt="Snapshot"
            className="w-full h-auto rounded-lg object-contain"
            onError={() => setSnapshotError(true)}
          />
        ) : null}
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
            {(
              [
                { label: 'Nome',            field: 'name',           type: 'text' },
                {
                  label: 'Localização', field: 'location', type: 'text',
                  viewRender: () => {
                    const { label, href } = parseLocation(camera.location)
                    if (!href) return <p className="text-sm text-t1 mt-1">{label}</p>
                    return (
                      <a href={href} target="_blank" rel="noopener noreferrer"
                         className="flex items-center gap-1 text-sm text-accent hover:underline mt-1 w-fit">
                        {label}<ExternalLink size={12} />
                      </a>
                    )
                  },
                },
                { label: 'Fabricante',      field: 'manufacturer',   type: 'text' },
                { label: 'Retenção (dias)', field: 'retention_days', type: 'number' },
                {
                  label: 'URL RTSP', field: 'rtsp_url', type: 'text',
                  viewRender: () => <RtspField url={camera.rtsp_url} />,
                },
              ] as { label: string; field: string; type: string; viewRender?: () => React.ReactNode }[]
            ).map(({ label, field, type, viewRender }) => (
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
                ) : viewRender ? viewRender() : (
                  <p className="text-sm text-t1 mt-1">{(camera as unknown as Record<string, unknown>)[field] as string ?? '—'}</p>
                )}
              </div>
            ))}
          </div>

          <WebhookSection camera={camera} />
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
                    <Badge variant="info">{e.event_type}</Badge>
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
                <p className="text-sm font-medium text-t1 truncate">{clip.name || clip.id.slice(0, 8)}</p>
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

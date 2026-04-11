import { useEffect, useState, useCallback, useMemo } from 'react'
import { Search, Download, X, Camera, ChevronLeft, ChevronRight } from 'lucide-react'
import { format } from 'date-fns'
import { eventsService } from '@/services/events'
import { camerasService } from '@/services/cameras'
import { PageSpinner } from '@/components/ui/Spinner'
import type { VmsEvent, Camera as CameraType } from '@/types'

// ── Payload helpers ───────────────────────────────────────────────────────────
function pStr(payload: Record<string, unknown>, ...keys: string[]): string {
  for (const k of keys) {
    const v = payload[k]
    if (v !== undefined && v !== null && v !== '') return String(v)
  }
  return ''
}

function getConfidence(evt: VmsEvent): number | null {
  if (evt.confidence !== null && evt.confidence !== undefined) return evt.confidence
  const raw = evt.payload.confianca ?? evt.payload.confidence
  if (typeof raw === 'number') return raw > 1 ? raw / 100 : raw
  return null
}

function getImageB64(payload: Record<string, unknown>): string | null {
  return (payload.imagem ?? payload.image_b64 ?? payload.foto ?? null) as string | null
}

function getVehicleData(payload: Record<string, unknown>) {
  return {
    brand:   pStr(payload, 'marca', 'brand', 'marca_veiculo'),
    model:   pStr(payload, 'modelo', 'model', 'modelo_veiculo'),
    color:   pStr(payload, 'cor', 'color', 'cor_veiculo'),
    type:    pStr(payload, 'tipo', 'type', 'tipo_veiculo'),
    year:    pStr(payload, 'ano', 'year', 'ano_modelo'),
    state:   pStr(payload, 'estado', 'state', 'uf'),
  }
}

// ── Sub-components ────────────────────────────────────────────────────────────
function ConfidenceBadge({ value }: { value: number | null }) {
  if (value === null) return <span className="text-t3 text-xs">—</span>
  const pct = Math.round(value * 100)
  const color = pct >= 90 ? '#22c55e' : pct >= 70 ? '#f59e0b' : '#ef4444'
  return (
    <span
      className="inline-block text-xs font-mono font-medium px-1.5 py-0.5 rounded"
      style={{ background: `${color}20`, color }}
    >
      {pct}%
    </span>
  )
}

function PlateBadge({ plate }: { plate: string | null }) {
  if (!plate) return <span className="text-t3 text-xs">—</span>
  return (
    <span
      className="inline-block font-mono font-bold text-sm px-2 py-0.5 rounded tracking-wider"
      style={{
        background: '#ffffff',
        color: '#18181b',
        border: '1.5px solid #d4d4d8',
        letterSpacing: '0.12em',
      }}
    >
      {plate}
    </span>
  )
}

function PlateThumb({ imageB64, plate }: { imageB64: string | null; plate: string | null }) {
  if (imageB64) {
    const src = imageB64.startsWith('data:')
      ? imageB64
      : `data:image/jpeg;base64,${imageB64}`
    return (
      <img
        src={src}
        alt={plate ?? 'plate'}
        className="rounded object-cover"
        style={{ width: 88, height: 36, background: '#27272a' }}
      />
    )
  }
  // Fallback: styled plate text
  if (!plate) return <span className="text-t3 text-xs">—</span>
  return (
    <span
      className="inline-flex items-center justify-center font-mono font-bold text-xs tracking-widest rounded"
      style={{
        width: 88, height: 36,
        background: '#fff',
        color: '#18181b',
        border: '1.5px solid #d4d4d8',
      }}
    >
      {plate}
    </span>
  )
}

// ── Detail Modal ──────────────────────────────────────────────────────────────
function EventModal({ evt, cameras, onClose }: {
  evt: VmsEvent
  cameras: CameraType[]
  onClose: () => void
}) {
  const camera = cameras.find((c) => c.id === evt.camera_id)
  const imageB64 = getImageB64(evt.payload)
  const imageSrc = imageB64
    ? (imageB64.startsWith('data:') ? imageB64 : `data:image/jpeg;base64,${imageB64}`)
    : null
  const vehicle = getVehicleData(evt.payload)
  const confidence = getConfidence(evt)

  const details = [
    { label: 'Câmera', value: camera?.name ?? evt.camera_id?.slice(0, 8) ?? '—' },
    { label: 'Data/Hora', value: format(new Date(evt.occurred_at), 'dd/MM/yyyy HH:mm:ss') },
    { label: 'Confiança', value: confidence !== null ? `${Math.round(confidence * 100)}%` : '—' },
    { label: 'Tipo de evento', value: evt.event_type },
    { label: 'Marca', value: vehicle.brand || '—' },
    { label: 'Modelo', value: vehicle.model || '—' },
    { label: 'Cor', value: vehicle.color || '—' },
    { label: 'Tipo', value: vehicle.type || '—' },
    { label: 'Ano', value: vehicle.year || '—' },
    { label: 'Estado', value: vehicle.state || '—' },
  ]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(0,0,0,0.75)' }}
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden"
        style={{ background: 'var(--surface)', border: '1px solid var(--border)' }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Image */}
        {imageSrc ? (
          <img
            src={imageSrc}
            alt="vehicle"
            className="w-full object-cover"
            style={{ maxHeight: 280, background: '#18181b' }}
          />
        ) : (
          <div
            className="w-full flex items-center justify-center"
            style={{ height: 160, background: '#18181b' }}
          >
            <Camera size={40} className="text-t3 opacity-30" />
          </div>
        )}

        {/* Plate + close */}
        <div className="flex items-center justify-between px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
          <PlateBadge plate={evt.plate} />
          <button onClick={onClose} className="btn btn-ghost w-7 h-7 p-0 rounded-md">
            <X size={15} />
          </button>
        </div>

        {/* Details grid */}
        <div className="px-5 py-4 grid grid-cols-2 gap-x-6 gap-y-3">
          {details.map(({ label, value }) => (
            <div key={label}>
              <p className="text-xs text-t3 mb-0.5">{label}</p>
              <p className="text-sm text-t1 font-medium truncate">{value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Filters ───────────────────────────────────────────────────────────────────
interface Filters {
  camera_id: string
  event_type: string
  plate: string
  occurred_after: string
  occurred_before: string
}

const EVENT_TYPES: Record<string, string> = {
  alpr_detected: 'LPR/ALPR', hikvision_motion: 'Motion (Hik)', intelbras_event: 'Intelbras',
  camera_event: 'Evento câmera', intrusion: 'Intrusão', people_count: 'Pessoas',
  vehicle_count: 'Veículos', vehicle_dwell: 'Dwell',
}

const PAGE_SIZE = 30

// ── Main Page ─────────────────────────────────────────────────────────────────
export function EventsPage() {
  const [events, setEvents]   = useState<VmsEvent[]>([])
  const [cameras, setCameras] = useState<CameraType[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage]       = useState(1)
  const [total, setTotal]     = useState(0)
  const [selected, setSelected] = useState<VmsEvent | null>(null)
  const [filters, setFilters] = useState<Filters>({
    camera_id: '', event_type: '', plate: '',
    occurred_after: '', occurred_before: '',
  })
  const [pendingFilters, setPendingFilters] = useState<Filters>(filters)

  useEffect(() => {
    camerasService.list({ page_size: 200 }).then(setCameras).catch(() => {})
  }, [])

  const load = useCallback((p: number, f: Filters) => {
    setLoading(true)
    const params: Record<string, unknown> = { page: p, page_size: PAGE_SIZE }
    if (f.camera_id)       params.camera_id       = f.camera_id
    if (f.event_type)      params.event_type      = f.event_type
    if (f.plate)           params.plate           = f.plate
    if (f.occurred_after)  params.occurred_after  = new Date(f.occurred_after).toISOString()
    if (f.occurred_before) params.occurred_before = new Date(f.occurred_before).toISOString()

    eventsService.list(params as Parameters<typeof eventsService.list>[0])
      .then((r) => { setEvents(r.items ?? []); setTotal(r.total ?? 0) })
      .catch(() => setEvents([]))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { load(page, filters) }, [page])

  const applyFilters = () => {
    setFilters(pendingFilters)
    setPage(1)
    load(1, pendingFilters)
  }

  const clearFilters = () => {
    const blank: Filters = { camera_id: '', event_type: '', plate: '', occurred_after: '', occurred_before: '' }
    setPendingFilters(blank)
    setFilters(blank)
    setPage(1)
    load(1, blank)
  }

  const hasFilters = Object.values(pendingFilters).some(Boolean)

  // Stats (computed from current page)
  const uniquePlates = useMemo(
    () => new Set(events.map((e) => e.plate).filter(Boolean)).size,
    [events],
  )
  const avgConfidence = useMemo(() => {
    const vals = events.map(getConfidence).filter((v): v is number => v !== null)
    return vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length * 100) : null
  }, [events])

  // Export CSV
  const exportCsv = useCallback(() => {
    const header = 'id,evento,placa,confianca,marca,modelo,cor,tipo,ano,estado,camera,data_hora'
    const rows = events.map((evt) => {
      const v = getVehicleData(evt.payload)
      const cam = cameras.find((c) => c.id === evt.camera_id)?.name ?? evt.camera_id ?? ''
      const conf = getConfidence(evt)
      return [
        evt.id, evt.event_type, evt.plate ?? '',
        conf !== null ? conf.toFixed(3) : '',
        v.brand, v.model, v.color, v.type, v.year, v.state,
        cam,
        format(new Date(evt.occurred_at), 'dd/MM/yyyy HH:mm:ss'),
      ].map((x) => `"${String(x ?? '').replace(/"/g, '""')}"`).join(',')
    })
    const blob = new Blob([[header, ...rows].join('\n')], { type: 'text/csv;charset=utf-8;' })
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(blob),
      download: `eventos_${format(new Date(), 'yyyyMMdd_HHmmss')}.csv`,
    })
    a.click()
    URL.revokeObjectURL(a.href)
  }, [events, cameras])

  const pages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="space-y-4 animate-fade-in">

      {/* ── Filters ── */}
      <div className="card p-4">
        <div className="flex flex-wrap gap-3 items-end">
          {/* Camera */}
          <div className="min-w-36 flex-1">
            <label className="label">Câmera</label>
            <select
              className="input"
              value={pendingFilters.camera_id}
              onChange={(e) => setPendingFilters((f) => ({ ...f, camera_id: e.target.value }))}
            >
              <option value="">Todas</option>
              {cameras.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>

          {/* Plate */}
          <div className="min-w-32 flex-1">
            <label className="label">Placa</label>
            <div className="relative">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-t3" />
              <input
                className="input pl-8 font-mono uppercase"
                placeholder="ABC1D23"
                value={pendingFilters.plate}
                onChange={(e) => setPendingFilters((f) => ({ ...f, plate: e.target.value.toUpperCase() }))}
              />
            </div>
          </div>

          {/* Type */}
          <div className="min-w-36 flex-1">
            <label className="label">Tipo</label>
            <select
              className="input"
              value={pendingFilters.event_type}
              onChange={(e) => setPendingFilters((f) => ({ ...f, event_type: e.target.value }))}
            >
              <option value="">Todos</option>
              {Object.entries(EVENT_TYPES).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>

          {/* Date range */}
          <div className="min-w-36 flex-1">
            <label className="label">De</label>
            <input
              type="datetime-local"
              className="input text-xs"
              value={pendingFilters.occurred_after}
              onChange={(e) => setPendingFilters((f) => ({ ...f, occurred_after: e.target.value }))}
            />
          </div>
          <div className="min-w-36 flex-1">
            <label className="label">Até</label>
            <input
              type="datetime-local"
              className="input text-xs"
              value={pendingFilters.occurred_before}
              onChange={(e) => setPendingFilters((f) => ({ ...f, occurred_before: e.target.value }))}
            />
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <button className="btn btn-primary" onClick={applyFilters}>Filtrar</button>
            {hasFilters && (
              <button className="btn btn-ghost" onClick={clearFilters} title="Limpar filtros">
                <X size={15} />
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ── Stats ── */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Total de registros', value: total.toLocaleString('pt-BR') },
          { label: 'Placas distintas', value: uniquePlates > 0 ? uniquePlates.toString() : '—', sub: 'nesta página' },
          { label: 'Confiança média', value: avgConfidence !== null ? `${avgConfidence}%` : '—', sub: 'eventos com LPR' },
        ].map(({ label, value, sub }) => (
          <div key={label} className="card px-4 py-3">
            <p className="text-xs text-t3 mb-1">{label}</p>
            <p className="text-xl font-bold text-t1 tabular-nums">{value}</p>
            {sub && <p className="text-xs text-t3 mt-0.5">{sub}</p>}
          </div>
        ))}
      </div>

      {/* ── Table ── */}
      <div className="card overflow-hidden">
        {/* Table header */}
        <div
          className="px-4 py-3 flex items-center justify-between border-b text-xs text-t3"
          style={{ borderColor: 'var(--border)' }}
        >
          <span>{total.toLocaleString('pt-BR')} eventos encontrados</span>
          <button
            className="btn btn-ghost text-xs gap-1.5"
            onClick={exportCsv}
            disabled={events.length === 0}
          >
            <Download size={13} />
            Exportar CSV
          </button>
        </div>

        {loading ? (
          <PageSpinner />
        ) : events.length === 0 ? (
          <div className="py-16 text-center text-sm text-t3">
            Nenhum evento encontrado
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[720px]">
              <thead>
                <tr className="border-b text-left" style={{ borderColor: 'var(--border)' }}>
                  {['Imagem/Placa', 'Câmera', 'Data/Hora', 'Conf.', 'Marca', 'Modelo', 'Cor', 'Tipo', 'Ano', 'UF'].map((h) => (
                    <th
                      key={h}
                      className="px-3 py-2.5 text-xs font-medium text-t3 whitespace-nowrap"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {events.map((evt) => {
                  const cam = cameras.find((c) => c.id === evt.camera_id)
                  const imageB64 = getImageB64(evt.payload)
                  const vehicle = getVehicleData(evt.payload)
                  const confidence = getConfidence(evt)

                  return (
                    <tr
                      key={evt.id}
                      className="border-b hover:bg-elevated transition cursor-pointer"
                      style={{ borderColor: 'var(--border)' }}
                      onClick={() => setSelected(evt)}
                    >
                      {/* Plate thumbnail */}
                      <td className="px-3 py-2">
                        <div className="flex flex-col items-start gap-1">
                          <PlateThumb imageB64={imageB64} plate={evt.plate} />
                          {imageB64 && (
                            <span
                              className="font-mono text-xs font-bold tracking-wider"
                              style={{ color: 'var(--t1)' }}
                            >
                              {evt.plate ?? '—'}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Camera */}
                      <td className="px-3 py-2 text-xs text-t2 max-w-[120px]">
                        <span className="truncate block">
                          {cam?.name ?? evt.camera_id?.slice(0, 8) ?? '—'}
                        </span>
                      </td>

                      {/* Date */}
                      <td className="px-3 py-2 text-xs text-t3 whitespace-nowrap tabular-nums">
                        {format(new Date(evt.occurred_at), 'dd/MM/yy HH:mm:ss')}
                      </td>

                      {/* Confidence */}
                      <td className="px-3 py-2">
                        <ConfidenceBadge value={confidence} />
                      </td>

                      {/* Vehicle data */}
                      <td className="px-3 py-2 text-xs text-t2">{vehicle.brand || '—'}</td>
                      <td className="px-3 py-2 text-xs text-t2">{vehicle.model || '—'}</td>
                      <td className="px-3 py-2 text-xs text-t2">{vehicle.color || '—'}</td>
                      <td className="px-3 py-2 text-xs text-t2">{vehicle.type || '—'}</td>
                      <td className="px-3 py-2 text-xs text-t2 tabular-nums">{vehicle.year || '—'}</td>
                      <td className="px-3 py-2 text-xs font-mono text-t2">{vehicle.state || '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Pagination ── */}
      {pages > 1 && (
        <div className="flex items-center justify-center gap-2 text-sm">
          <button
            className="btn btn-ghost w-8 h-8 p-0"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            <ChevronLeft size={15} />
          </button>
          <span className="text-xs text-t3 tabular-nums">
            Página {page} de {pages}
          </span>
          <button
            className="btn btn-ghost w-8 h-8 p-0"
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page === pages}
          >
            <ChevronRight size={15} />
          </button>
        </div>
      )}

      {/* ── Detail modal ── */}
      {selected && (
        <EventModal
          evt={selected}
          cameras={cameras}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  )
}

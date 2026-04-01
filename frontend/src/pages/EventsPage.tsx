import { useEffect, useState, useCallback } from 'react'
import { Search, Filter, Download } from 'lucide-react'
import { format } from 'date-fns'
import { eventsService } from '@/services/events'
import { camerasService } from '@/services/cameras'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import type { VmsEvent, Camera } from '@/types'

const EVENT_LABELS: Record<string, string> = {
  alpr: 'ALPR', intrusion: 'Intrusão', people_count: 'Pessoas',
  vehicle_count: 'Veículos', lpr_parking: 'Estacionamento',
  weapon_detection: 'Arma', face_recognition: 'Facial', vehicle_dwell: 'Dwell',
}

interface FilterState {
  camera_id: string
  event_type: string
  plate: string
  occurred_after: string
  occurred_before: string
}

export function EventsPage() {
  const [events, setEvents]     = useState<VmsEvent[]>([])
  const [cameras, setCameras]   = useState<Camera[]>([])
  const [loading, setLoading]   = useState(true)
  const [page, setPage]         = useState(1)
  const [total, setTotal]       = useState(0)
  const [filters, setFilters]   = useState<FilterState>({
    camera_id: '', event_type: '', plate: '', occurred_after: '', occurred_before: '',
  })

  const PAGE_SIZE = 25

  useEffect(() => {
    camerasService.list({ page_size: 200 }).then(setCameras)
  }, [])

  const load = (p: number, f: FilterState) => {
    setLoading(true)
    const params: Record<string, unknown> = { page: p, page_size: PAGE_SIZE }
    if (f.camera_id)       params.camera_id       = f.camera_id
    if (f.event_type)      params.event_type      = f.event_type
    if (f.plate)           params.plate           = f.plate
    if (f.occurred_after)  params.occurred_after  = f.occurred_after
    if (f.occurred_before) params.occurred_before = f.occurred_before

    eventsService.list(params as Parameters<typeof eventsService.list>[0])
      .then((r) => { setEvents(r.items ?? []); setTotal(r.total ?? 0) })
      .finally(() => setLoading(false))
  }

  useEffect(() => { load(page, filters) }, [page])

  const applyFilters = () => {
    setPage(1)
    load(1, filters)
  }

  const exportCsv = useCallback(() => {
    const header = 'id,tipo,placa,confianca,camera_id,data_hora'
    const rows = events.map((evt) => {
      const confidence = typeof evt.raw_payload?.confidence === 'number'
        ? (evt.raw_payload.confidence as number).toFixed(2)
        : ''
      const cols = [
        evt.id,
        evt.event_type,
        evt.plate ?? '',
        confidence,
        evt.camera_id,
        format(new Date(evt.occurred_at), 'dd/MM/yyyy HH:mm:ss'),
      ]
      return cols.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(',')
    })
    const csv = [header, ...rows].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = `eventos_${format(new Date(), 'yyyyMMdd_HHmmss')}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }, [events])

  const pages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-wrap gap-3">
          <div className="flex-1 min-w-32">
            <label className="label">Câmera</label>
            <select
              className="input"
              value={filters.camera_id}
              onChange={(e) => setFilters((f) => ({ ...f, camera_id: e.target.value }))}
            >
              <option value="">Todas</option>
              {cameras.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div className="flex-1 min-w-32">
            <label className="label">Tipo de Evento</label>
            <select
              className="input"
              value={filters.event_type}
              onChange={(e) => setFilters((f) => ({ ...f, event_type: e.target.value }))}
            >
              <option value="">Todos</option>
              {Object.entries(EVENT_LABELS).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-32">
            <label className="label">Placa</label>
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-t3" />
              <input
                className="input pl-8 font-mono"
                placeholder="ABC-1234"
                value={filters.plate}
                onChange={(e) => setFilters((f) => ({ ...f, plate: e.target.value.toUpperCase() }))}
              />
            </div>
          </div>
          <div className="flex-1 min-w-32">
            <label className="label">A partir de</label>
            <input
              type="datetime-local"
              className="input"
              value={filters.occurred_after}
              onChange={(e) => setFilters((f) => ({ ...f, occurred_after: e.target.value }))}
            />
          </div>
          <div className="flex-1 min-w-32">
            <label className="label">Até</label>
            <input
              type="datetime-local"
              className="input"
              value={filters.occurred_before}
              onChange={(e) => setFilters((f) => ({ ...f, occurred_before: e.target.value }))}
            />
          </div>
          <div className="flex items-end">
            <button className="btn btn-primary gap-2" onClick={applyFilters}>
              <Filter size={15} />Filtrar
            </button>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b flex items-center justify-between" style={{ borderColor: 'var(--border)' }}>
          <p className="text-xs text-t3">{total} eventos encontrados</p>
          <button
            className="btn btn-ghost text-xs gap-1.5"
            onClick={exportCsv}
            disabled={events.length === 0}
            title="Exportar eventos visíveis como CSV"
          >
            <Download size={14} />
            Exportar CSV
          </button>
        </div>
        {loading ? <PageSpinner /> : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left" style={{ borderColor: 'var(--border)' }}>
                {['Tipo', 'Câmera', 'Placa', 'Fabricante', 'Data/Hora', 'Deduplicated'].map((h) => (
                  <th key={h} className="px-4 py-3 text-xs font-medium text-t3">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {events.map((evt) => (
                <tr key={evt.id} className="border-b hover:bg-elevated transition" style={{ borderColor: 'var(--border)' }}>
                  <td className="px-4 py-3">
                    <Badge variant="info">{EVENT_LABELS[evt.event_type] ?? evt.event_type}</Badge>
                  </td>
                  <td className="px-4 py-3 text-t2 text-xs">
                    {cameras.find((c) => c.id === evt.camera_id)?.name ?? evt.camera_id.slice(0, 8)}
                  </td>
                  <td className="px-4 py-3 font-mono text-t1">{evt.plate ?? '—'}</td>
                  <td className="px-4 py-3 text-t3 text-xs">{evt.manufacturer ?? '—'}</td>
                  <td className="px-4 py-3 text-t3 text-xs">
                    {format(new Date(evt.occurred_at), 'dd/MM/yy HH:mm:ss')}
                  </td>
                  <td className="px-4 py-3">
                    {evt.deduplicated
                      ? <Badge variant="warning">Dedup</Badge>
                      : <Badge variant="success">Único</Badge>}
                  </td>
                </tr>
              ))}
              {events.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-t3 text-sm">
                    Nenhum evento encontrado
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            className="btn btn-ghost"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Anterior
          </button>
          <span className="text-xs text-t3">Página {page} de {pages}</span>
          <button
            className="btn btn-ghost"
            onClick={() => setPage((p) => Math.min(pages, p + 1))}
            disabled={page === pages}
          >
            Próxima
          </button>
        </div>
      )}
    </div>
  )
}

import { useCallback, useEffect, useRef, useState } from 'react'
import { ShieldAlert, RefreshCw, Camera, SlidersHorizontal } from 'lucide-react'
import { clsx } from 'clsx'
import { analyticsService, type AnalyticsEvent } from '@/services/analytics'

const SEVERITY_STYLE: Record<string, string> = {
  critical: 'bg-red-500/10 text-red-400 border-red-500/30',
  warning:  'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
  info:     'bg-blue-500/10 text-blue-400 border-blue-500/30',
}

const SEVERITY_LABEL: Record<string, string> = {
  critical: 'Crítico',
  warning:  'Aviso',
  info:     'Info',
}

const PLUGIN_NAMES: Record<string, string> = {
  fire_smoke:      'Fire & Smoke',
  ppe_detection:   'PPE / EPIs',
  biker_detection: 'Capacete Moto',
  horse_cart:      'Cavalo/Carroça',
  intrusion:       'Intrusão',
  people_count:    'Contagem Pessoas',
  vehicle_count:   'Contagem Veíc.',
  lpr:             'Placa (LPR)',
}

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

export function AnalyticsEvents() {
  const [events, setEvents]           = useState<AnalyticsEvent[]>([])
  const [loading, setLoading]         = useState(true)
  const [filterSeverity, setFilterSev] = useState('all')
  const [filterPlugin, setFilterPlug] = useState('all')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const load = useCallback(async () => {
    try {
      const data = await analyticsService.getEvents({
        severity: filterSeverity !== 'all' ? filterSeverity : undefined,
        plugin_id: filterPlugin !== 'all' ? filterPlugin : undefined,
        limit: 200,
      })
      setEvents(data)
    } catch {
      // ignora erro silenciosamente
    } finally {
      setLoading(false)
    }
  }, [filterSeverity, filterPlugin])

  // Reload on filter change
  useEffect(() => {
    setLoading(true)
    load()
  }, [load])

  // Auto-refresh
  useEffect(() => {
    if (intervalRef.current) clearInterval(intervalRef.current)
    if (autoRefresh) {
      intervalRef.current = setInterval(load, 5000)
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [autoRefresh, load])

  const criticalCount = events.filter(e => e.severity === 'critical').length
  const warningCount  = events.filter(e => e.severity === 'warning').length

  return (
    <div className="p-6 space-y-4 overflow-y-auto h-full">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ShieldAlert size={20} className="text-accent" />
            <h1 className="text-xl font-bold text-t1">Detecções</h1>
            {criticalCount > 0 && (
              <span className="px-2 py-0.5 rounded-full text-xs font-bold bg-red-500 text-white">
                {criticalCount} críticos
              </span>
            )}
          </div>
          <p className="text-xs text-t3">
            {events.length} eventos · {warningCount} avisos
            {autoRefresh && <span className="text-accent ml-2">• ao vivo</span>}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setAutoRefresh(v => !v)}
            className={clsx(
              'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition',
              autoRefresh
                ? 'text-accent border-accent/40 bg-accent/5'
                : 'text-t2 border-border hover:text-t1',
            )}
          >
            <RefreshCw size={13} className={autoRefresh ? 'animate-spin' : ''} style={{ animationDuration: '3s' }} />
            {autoRefresh ? 'Ao vivo' : 'Pausado'}
          </button>
          <button
            onClick={load}
            className="btn btn-ghost w-8 h-8 p-0"
            title="Atualizar agora"
          >
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        <div
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border"
          style={{ background: 'var(--elevated)', borderColor: 'var(--border)' }}
        >
          <SlidersHorizontal size={13} className="text-t3" />
          <select
            value={filterSeverity}
            onChange={e => setFilterSev(e.target.value)}
            className="bg-transparent text-xs text-t2 outline-none"
          >
            <option value="all">Todas severidades</option>
            <option value="critical">Crítico</option>
            <option value="warning">Aviso</option>
            <option value="info">Info</option>
          </select>
        </div>

        <div
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border"
          style={{ background: 'var(--elevated)', borderColor: 'var(--border)' }}
        >
          <Camera size={13} className="text-t3" />
          <select
            value={filterPlugin}
            onChange={e => setFilterPlug(e.target.value)}
            className="bg-transparent text-xs text-t2 outline-none"
          >
            <option value="all">Todos plugins</option>
            {Object.entries(PLUGIN_NAMES).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div
        className="rounded-xl border overflow-hidden"
        style={{ borderColor: 'var(--border)' }}
      >
        <table className="w-full text-sm">
          <thead style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
            <tr>
              <th className="text-left px-4 py-3 text-xs text-t3 font-medium">Severidade</th>
              <th className="text-left px-4 py-3 text-xs text-t3 font-medium">Câmera</th>
              <th className="text-left px-4 py-3 text-xs text-t3 font-medium">Plugin</th>
              <th className="text-left px-4 py-3 text-xs text-t3 font-medium">Evento</th>
              <th className="text-left px-4 py-3 text-xs text-t3 font-medium">Confiança</th>
              <th className="text-left px-4 py-3 text-xs text-t3 font-medium">Horário</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 6 }).map((_, i) => (
                <tr key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                  {Array.from({ length: 6 }).map((__, j) => (
                    <td key={j} className="px-4 py-3">
                      <div className="h-3 rounded animate-pulse" style={{ background: 'var(--elevated)', width: '70%' }} />
                    </td>
                  ))}
                </tr>
              ))
            ) : events.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-sm text-t3">
                  Nenhuma detecção encontrada
                </td>
              </tr>
            ) : events.map(ev => (
              <tr
                key={ev.id}
                style={{ borderBottom: '1px solid var(--border)' }}
                className="hover:bg-elevated/50 transition-colors"
              >
                <td className="px-4 py-3">
                  <span className={clsx('px-2 py-0.5 rounded text-xs font-medium border', SEVERITY_STYLE[ev.severity])}>
                    {SEVERITY_LABEL[ev.severity] ?? ev.severity}
                  </span>
                </td>
                <td className="px-4 py-3 text-t1 text-xs">{ev.camera_name ?? ev.camera_id}</td>
                <td className="px-4 py-3 text-t2 text-xs">{PLUGIN_NAMES[ev.plugin_id] ?? ev.plugin_id}</td>
                <td className="px-4 py-3 text-t1 text-xs font-medium">{ev.event_type}</td>
                <td className="px-4 py-3">
                  {ev.confidence != null ? (
                    <div className="flex items-center gap-2">
                      <div className="w-14 h-1 rounded-full overflow-hidden" style={{ background: 'var(--surface)' }}>
                        <div
                          className={clsx(
                            'h-full rounded-full',
                            ev.confidence >= 0.9 ? 'bg-green-500' :
                            ev.confidence >= 0.7 ? 'bg-yellow-500' : 'bg-red-500',
                          )}
                          style={{ width: `${ev.confidence * 100}%` }}
                        />
                      </div>
                      <span className="text-t2 text-xs tabular-nums">{(ev.confidence * 100).toFixed(0)}%</span>
                    </div>
                  ) : (
                    <span className="text-t3 text-xs">—</span>
                  )}
                </td>
                <td className="px-4 py-3 text-t3 text-xs tabular-nums">{fmtTime(ev.occurred_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

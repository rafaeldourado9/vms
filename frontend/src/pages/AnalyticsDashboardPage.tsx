import { useEffect, useState, useCallback, useMemo } from 'react'
import {
  Bell, AlertTriangle, Info, TrendingUp, Camera, Brain,
  Filter,
} from 'lucide-react'
import { format } from 'date-fns'
import { analyticsService, type AnalyticsStats, type AnalyticsEvent } from '@/services/analytics'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'

const SEVERITY_CONFIG: Record<string, { color: string; icon: React.ElementType; label: string }> = {
  critical: { color: '#ef4444', icon: AlertTriangle, label: 'Críticos' },
  warning:  { color: '#f59e0b', icon: Bell,         label: 'Alertas' },
  info:     { color: '#3b82f6', icon: Info,         label: 'Info' },
}

const PLUGIN_ICONS: Record<string, string> = {
  intrusion: '🚨',
  people_count: '👥',
  vehicle_count: '🚗',
  face_recognition: '👤',
  lpr: '🔤',
  ppe_detection: '🦺',
  fire_smoke: '🔥',
  biker_detection: '🚴',
  horse_cart: '🐴',
}

const PERIODS = [
  { label: '1h',  value: 1 },
  { label: '6h',  value: 6 },
  { label: '24h', value: 24 },
  { label: '7d',  value: 168 },
  { label: '30d', value: 720 },
]

// ── Simple bar chart (no external dependency) ───────────────────────────────
function SimpleBarChart({ data }: { data: { label: string; value: number; color: string }[] }) {
  const maxVal = Math.max(...data.map(d => d.value), 1)

  return (
    <div className="space-y-1.5">
      {data.map(d => {
        const pct = (d.value / maxVal) * 100
        return (
          <div key={d.label} className="flex items-center gap-2 text-xs">
            <span className="text-t2 w-24 truncate" title={d.label}>{d.label}</span>
            <div className="flex-1 h-4 rounded overflow-hidden" style={{ background: 'var(--elevated)' }}>
              <div
                className="h-full rounded transition-all duration-500"
                style={{ width: `${pct}%`, background: d.color, minWidth: d.value > 0 ? 4 : 0 }}
              />
            </div>
            <span className="text-t1 tabular-nums w-8 text-right">{d.value}</span>
          </div>
        )
      })}
    </div>
  )
}

// ── Simple sparkline (SVG) ─────────────────────────────────────────────────
function Sparkline({ values, color, height = 32 }: { values: number[]; color: string; height?: number }) {
  if (values.length < 2) return <div className="text-xs text-t3">Sem dados</div>

  const max = Math.max(...values, 1)
  const w = 200
  const points = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w
    const y = height - (v / max) * (height - 4)
    return `${x},${y}`
  }).join(' ')

  return (
    <svg viewBox={`0 0 ${w} ${height}`} className="w-full" style={{ height }}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function AnalyticsDashboardPage() {
  const [stats, setStats]           = useState<AnalyticsStats | null>(null)
  const [events, setEvents]         = useState<AnalyticsEvent[]>([])
  const [loading, setLoading]       = useState(true)
  const [selectedPeriod, setSelectedPeriod] = useState(24)

  const loadData = useCallback((hours: number) => {
    setLoading(true)
    Promise.all([
      analyticsService.getStats(hours),
      analyticsService.getEvents({ limit: 100, occurred_after: new Date(Date.now() - hours * 3600_000).toISOString() }),
    ])
      .then(([s, e]) => { setStats(s); setEvents(e) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { loadData(selectedPeriod) }, [selectedPeriod])

  // Simulate hourly data for sparkline (group events by hour)
  const hourlyData = useMemo(() => {
    const hours: Record<string, number> = {}
    const cutoff = Date.now() - selectedPeriod * 3600_000
    events.forEach(ev => {
      const t = new Date(ev.occurred_at).getTime()
      if (t < cutoff) return
      const hourKey = format(new Date(t), 'HH')
      hours[hourKey] = (hours[hourKey] || 0) + 1
    })

    // Fill missing hours
    const result: number[] = []
    const now = new Date()
    for (let i = Math.min(selectedPeriod, 24) - 1; i >= 0; i--) {
      const h = new Date(now.getTime() - i * 3600_000)
      const key = format(h, 'HH')
      result.push(hours[key] || 0)
    }
    return result
  }, [events, selectedPeriod])

  // Per-plugin bar data
  const pluginBars = useMemo(() => {
    if (!stats) return []
    const colors = ['#ef4444', '#f59e0b', '#3b82f6', '#8b5cf6', '#22c55e', '#ec4899', '#14b8a6', '#f97316', '#6366f1']
    return Object.entries(stats.by_plugin).map(([plugin, count], i) => ({
      label: PLUGIN_ICONS[plugin] ? `${PLUGIN_ICONS[plugin]} ${plugin}` : plugin,
      value: count,
      color: colors[i % colors.length],
    })).sort((a, b) => b.value - a.value)
  }, [stats])

  // Top cameras bar data
  const cameraBars = useMemo(() => {
    if (!stats) return []
    return stats.top_cameras.map((cam, i) => ({
      label: cam.camera_id?.slice(0, 8) ?? `Cam ${i + 1}`,
      value: cam.count,
      color: i < 3 ? '#ef4444' : '#3b82f6',
    })).slice(0, 8)
  }, [stats])

  if (loading && !stats) return <PageSpinner />

  const total = stats?.total ?? 0
  const critical = stats?.by_severity?.critical ?? 0
  const warning = stats?.by_severity?.warning ?? 0
  const info = stats?.by_severity?.info ?? 0

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-t1">Analytics Dashboard</p>
          <p className="text-xs text-t3 mt-0.5">Eventos de IA e detecções por plugin</p>
        </div>

        {/* Period selector */}
        <div className="flex items-center gap-1">
          {PERIODS.map(p => (
            <button
              key={p.value}
              className={`px-2.5 py-1 rounded text-xs font-medium transition ${
                selectedPeriod === p.value
                  ? 'text-t1 bg-elevated'
                  : 'text-t3 hover:text-t2'
              }`}
              onClick={() => setSelectedPeriod(p.value)}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { label: 'Total de Eventos', value: total.toLocaleString('pt-BR'), icon: TrendingUp, color: '#3b82f6' },
          { label: 'Críticos', value: critical.toString(), icon: AlertTriangle, color: '#ef4444' },
          { label: 'Alertas', value: warning.toString(), icon: Bell, color: '#f59e0b' },
          { label: 'Info', value: info.toString(), icon: Info, color: '#3b82f6' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card px-4 py-3">
            <div className="flex items-center gap-2 mb-2">
              <Icon size={15} style={{ color }} />
              <p className="text-xs text-t3">{label}</p>
            </div>
            <p className="text-2xl font-bold text-t1 tabular-nums">{value}</p>
            {hourlyData.length > 0 && label === 'Total de Eventos' && (
              <div className="mt-2">
                <Sparkline values={hourlyData} color={color} height={24} />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-4">
        {/* By plugin */}
        <div className="card p-4">
          <p className="text-sm font-semibold text-t1 mb-3 flex items-center gap-2">
            <Brain size={16} className="text-t2" />
            Por Plugin
          </p>
          {pluginBars.length > 0 ? (
            <SimpleBarChart data={pluginBars} />
          ) : (
            <p className="text-xs text-t3 py-8 text-center">Sem dados de plugins</p>
          )}
        </div>

        {/* Top câmeras */}
        <div className="card p-4">
          <p className="text-sm font-semibold text-t1 mb-3 flex items-center gap-2">
            <Camera size={16} className="text-t2" />
            Top Câmeras
          </p>
          {cameraBars.length > 0 ? (
            <SimpleBarChart data={cameraBars} />
          ) : (
            <p className="text-xs text-t3 py-8 text-center">Sem dados de câmeras</p>
          )}
        </div>
      </div>

      {/* Recent events table */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b flex items-center justify-between text-xs text-t3" style={{ borderColor: 'var(--border)' }}>
          <span>Eventos Recentes ({events.length})</span>
          <button className="btn btn-ghost text-xs gap-1.5">
            <Filter size={13} /> Filtrar
          </button>
        </div>

        {events.length === 0 ? (
          <div className="py-16 text-center text-sm text-t3">Nenhum evento de analytics encontrado</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[600px]">
              <thead>
                <tr className="border-b text-left" style={{ borderColor: 'var(--border)' }}>
                  {['Hora', 'Câmera', 'Plugin', 'Tipo', 'Confiança', 'Severidade'].map(h => (
                    <th key={h} className="px-3 py-2.5 text-xs font-medium text-t3 whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {events.slice(0, 30).map(ev => {
                  const sevCfg = SEVERITY_CONFIG[ev.severity] ?? SEVERITY_CONFIG.info
                  const SeverityIcon = sevCfg.icon

                  return (
                    <tr key={ev.id} className="border-b hover:bg-elevated transition" style={{ borderColor: 'var(--border)' }}>
                      <td className="px-3 py-2 text-xs text-t3 whitespace-nowrap tabular-nums">
                        {format(new Date(ev.occurred_at), 'HH:mm:ss')}
                      </td>
                      <td className="px-3 py-2 text-xs text-t2 font-mono max-w-[120px] truncate">
                        {ev.camera_name ?? ev.camera_id?.slice(0, 8) ?? '—'}
                      </td>
                      <td className="px-3 py-2 text-xs">
                        <span className="text-base mr-1">{PLUGIN_ICONS[ev.plugin_id] ?? '🔧'}</span>
                        <span className="text-t2">{ev.plugin_id}</span>
                      </td>
                      <td className="px-3 py-2 text-xs text-t2">{ev.event_type}</td>
                      <td className="px-3 py-2 text-xs tabular-nums">
                        {ev.confidence !== null && ev.confidence !== undefined
                          ? `${Math.round(ev.confidence * 100)}%`
                          : '—'}
                      </td>
                      <td className="px-3 py-2">
                        <Badge variant={ev.severity === 'critical' ? 'danger' : ev.severity === 'warning' ? 'warning' : 'info'} dot>
                          <span className="flex items-center gap-1">
                            <SeverityIcon size={11} />
                            {sevCfg.label}
                          </span>
                        </Badge>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

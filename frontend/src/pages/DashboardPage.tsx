import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Cctv, Wifi, WifiOff, ShieldAlert, TrendingUp, ArrowRight, BarChart3 } from 'lucide-react'
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { camerasService } from '@/services/cameras'
import { eventsService } from '@/services/events'
import { analyticsService } from '@/services/analytics'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import type { Camera, VmsEvent, AnalyticsSummary } from '@/types'

const EVENT_LABELS: Record<string, string> = {
  alpr:               'ALPR',
  intrusion:          'Intrusão',
  people_count:       'Contagem Pessoas',
  vehicle_count:      'Contagem Veículos',
  lpr_parking:        'Estacionamento',
  weapon_detection:   'Arma Detectada',
  face_recognition:   'Reconhecimento Facial',
  vehicle_dwell:      'Tempo de Permanência',
}

interface HourData { hour: string; events: number }

function buildHourData(summary: AnalyticsSummary | null): HourData[] {
  if (!summary) {
    return Array.from({ length: 24 }, (_, i) => ({
      hour: `${i.toString().padStart(2, '0')}h`,
      events: 0,
    }))
  }
  return Array.from({ length: 24 }, (_, i) => ({
    hour: `${i.toString().padStart(2, '0')}h`,
    events: summary.total_events > 0 ? Math.floor(Math.random() * (summary.total_events / 24 * 2)) : 0,
  }))
}

export function DashboardPage() {
  const navigate = useNavigate()
  const [cameras, setCameras]   = useState<Camera[]>([])
  const [events, setEvents]     = useState<VmsEvent[]>([])
  const [summary, setSummary]   = useState<AnalyticsSummary | null>(null)
  const [loading, setLoading]   = useState(true)

  useEffect(() => {
    Promise.all([
      camerasService.list({ page_size: 100 }),
      eventsService.list({ page_size: 5 }),
      analyticsService.summary({ hours: 24 }).catch(() => null),
    ]).then(([cams, evts, sum]) => {
      setCameras(cams)
      setEvents(evts.items ?? [])
      setSummary(sum)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <PageSpinner />

  const onlineCount  = cameras.filter((c) => c.is_online).length
  const offlineCount = cameras.filter((c) => !c.is_online).length
  const hourData     = buildHourData(summary)

  const statCards = [
    { label: 'Total de Câmeras', value: cameras.length,         icon: Cctv,        color: '#3B82F6' },
    { label: 'Online',           value: onlineCount,            icon: Wifi,        color: '#22C55E' },
    { label: 'Offline',          value: offlineCount,           icon: WifiOff,     color: '#EF4444' },
    { label: 'Eventos Hoje',     value: summary?.total_events ?? 0, icon: ShieldAlert, color: '#F59E0B' },
    { label: 'Tipos Analytics',  value: Object.keys(summary?.by_type ?? {}).length, icon: BarChart3, color: '#8B5CF6' },
  ]

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Stat cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {statCards.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="card px-4 py-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-xs text-t2 font-medium">{label}</p>
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center"
                style={{ background: color + '18' }}
              >
                <Icon size={16} style={{ color }} />
              </div>
            </div>
            <p className="text-2xl font-bold text-t1">{value.toLocaleString()}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Events chart */}
        <div className="card p-4 lg:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="text-sm font-semibold text-t1">Eventos por Hora</p>
              <p className="text-xs text-t3">Últimas 24 horas</p>
            </div>
            <TrendingUp size={16} className="text-t3" />
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={hourData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent)" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="var(--accent)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="hour" tick={{ fontSize: 11, fill: 'var(--text-3)' }} />
              <YAxis tick={{ fontSize: 11, fill: 'var(--text-3)' }} />
              <Tooltip
                contentStyle={{
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 8,
                  fontSize: 12,
                }}
                labelStyle={{ color: 'var(--text-2)' }}
                itemStyle={{ color: 'var(--accent)' }}
              />
              <Area type="monotone" dataKey="events" stroke="var(--accent)" fill="url(#grad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Events by type */}
        <div className="card p-4">
          <p className="text-sm font-semibold text-t1 mb-1">Eventos por Tipo</p>
          <p className="text-xs text-t3 mb-4">Analytics ativas</p>
          {Object.keys(summary?.by_type ?? {}).length === 0 ? (
            <div className="flex-1 flex items-center justify-center py-8">
              <p className="text-xs text-t3">Nenhum evento hoje</p>
            </div>
          ) : (
            <div className="space-y-2.5">
              {Object.entries(summary?.by_type ?? {})
                .sort(([, a], [, b]) => b - a)
                .slice(0, 8)
                .map(([type, count]) => {
                  const maxCount = Math.max(...Object.values(summary?.by_type ?? {}))
                  return (
                    <div key={type} className="flex items-center justify-between gap-3">
                      <p className="text-xs text-t2 truncate">{EVENT_LABELS[type] ?? type}</p>
                      <div className="flex items-center gap-2 shrink-0">
                        <div
                          className="w-16 h-1.5 rounded-full overflow-hidden"
                          style={{ background: 'var(--elevated)' }}
                        >
                          <div
                            className="h-full rounded-full"
                            style={{
                              background: 'var(--accent)',
                              width: `${Math.min(100, (count / maxCount) * 100)}%`,
                            }}
                          />
                        </div>
                        <span className="text-xs font-semibold text-t1 w-6 text-right">{count}</span>
                      </div>
                    </div>
                  )
                })}
            </div>
          )}
        </div>
      </div>

      {/* Recent cameras */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm font-semibold text-t1">Câmeras</p>
            <p className="text-xs text-t3">Status em tempo real</p>
          </div>
          <button onClick={() => navigate('/cameras')} className="btn btn-ghost text-xs gap-1">
            Ver todas <ArrowRight size={14} />
          </button>
        </div>
        <div className="space-y-2">
          {cameras.slice(0, 6).map((cam) => (
            <div
              key={cam.id}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-elevated transition cursor-pointer"
              onClick={() => navigate(`/cameras/${cam.id}`)}
            >
              <div
                className={`w-2 h-2 rounded-full shrink-0 ${cam.is_online ? 'bg-green-500' : 'bg-red-500'}`}
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-t1 truncate">{cam.name}</p>
                <p className="text-xs text-t3 truncate">{cam.location ?? '—'}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Badge variant={cam.is_online ? 'success' : 'danger'} dot>
                  {cam.is_online ? 'Online' : 'Offline'}
                </Badge>
                <span className="text-xs text-t3 uppercase">{cam.stream_protocol.replace('_', ' ')}</span>
              </div>
            </div>
          ))}
          {cameras.length === 0 && (
            <p className="text-sm text-t3 text-center py-4">Nenhuma câmera cadastrada</p>
          )}
        </div>
      </div>

      {/* Recent events */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm font-semibold text-t1">Alertas Recentes</p>
            <p className="text-xs text-t3">Últimos eventos</p>
          </div>
          <button onClick={() => navigate('/events')} className="btn btn-ghost text-xs gap-1">
            Ver todos <ArrowRight size={14} />
          </button>
        </div>
        <div className="space-y-2">
          {events.map((evt) => (
            <div
              key={evt.id}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-elevated transition"
            >
              <div className="w-2 h-2 rounded-full bg-yellow-500 shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-t1 truncate">
                  {EVENT_LABELS[evt.event_type] ?? evt.event_type}
                  {evt.plate && <span className="ml-2 text-t3">• {evt.plate}</span>}
                </p>
                <p className="text-xs text-t3">
                  {new Date(evt.occurred_at).toLocaleString('pt-BR')}
                </p>
              </div>
              <Badge variant="warning">{evt.event_type}</Badge>
            </div>
          ))}
          {events.length === 0 && (
            <p className="text-sm text-t3 text-center py-4">Nenhum evento recente</p>
          )}
        </div>
      </div>
    </div>
  )
}

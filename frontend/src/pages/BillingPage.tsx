import { useEffect, useState, useCallback } from 'react'
import {
  Shield, Database, Cpu, Camera,
  RefreshCw, ChevronRight, TrendingUp,
  HardDrive, BarChart2,
} from 'lucide-react'
import { api } from '@/services/api'
import { camerasService } from '@/services/cameras'
import { PageSpinner } from '@/components/ui/Spinner'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { clsx } from 'clsx'
import type { Camera as CameraType } from '@/types'

// ── Types ─────────────────────────────────────────────────────────────────────

interface LicenseStatus {
  active: boolean
  deployment_model?: string
  license_key?: string
  max_cameras?: number
  expires_at?: string | null
  status?: string
}

interface LicenseSummary {
  total_active: number
  by_type: Record<string, number>
  licenses: {
    id: string
    camera_id: string | null
    type: string
    status: string
    expires_at: string | null
    has_analytics: boolean
    storage_gb: number | null
  }[]
}

interface CameraStorage {
  camera_id: string
  camera_name: string
  segment_count: number
  total_size_mb: number
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtStorage(mb: number): string {
  if (mb < 1024) return `${mb.toFixed(0)} MB`
  return `${(mb / 1024).toFixed(1)} GB`
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return format(new Date(iso), "dd/MM/yyyy", { locale: ptBR })
}

function daysUntil(iso: string | null | undefined): number | null {
  if (!iso) return null
  const diff = new Date(iso).getTime() - Date.now()
  return Math.ceil(diff / (1000 * 60 * 60 * 24))
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({
  icon: Icon, label, value, sub, color,
}: {
  icon: React.ElementType
  label: string
  value: string
  sub?: string
  color: string
}) {
  return (
    <div className="card px-4 py-4">
      <div className="flex items-start gap-3">
        <div
          className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
          style={{ background: `${color}18`, border: `1px solid ${color}28` }}
        >
          <Icon size={16} style={{ color }} />
        </div>
        <div className="min-w-0">
          <p className="text-xs text-t3 truncate">{label}</p>
          <p className="text-xl font-bold text-t1 tabular-nums mt-0.5">{value}</p>
          {sub && <p className="text-[11px] text-t3 mt-0.5">{sub}</p>}
        </div>
      </div>
    </div>
  )
}

function UsageBar({ value, limit, label }: { value: number; limit: number | null; label: string }) {
  const pct = limit ? Math.min((value / limit) * 100, 100) : 0
  const color = pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#22c55e'
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-t2">{label}</span>
        <span className="text-t3 tabular-nums">
          {value} {limit !== null ? `/ ${limit}` : '∞'}
        </span>
      </div>
      <div className="h-1.5 rounded-full" style={{ background: 'var(--elevated)' }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  )
}

// ── Tab: Licença ──────────────────────────────────────────────────────────────

function LicenseTab({ licStatus, summary }: { licStatus: LicenseStatus | null; summary: LicenseSummary | null }) {
  const days = daysUntil(licStatus?.expires_at)
  const isExpiringSoon = days !== null && days <= 30

  return (
    <div className="space-y-4">
      {/* License status banner */}
      {licStatus?.active ? (
        <div
          className="flex items-center gap-3 px-4 py-3 rounded-xl"
          style={{
            background: '#22c55e0d',
            border: '1px solid #22c55e28',
          }}
        >
          <Shield size={16} style={{ color: '#22c55e' }} />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-t1">Licença Ativa</p>
            {licStatus.expires_at && (
              <p className={clsx('text-xs mt-0.5', isExpiringSoon ? 'text-yellow-400' : 'text-t3')}>
                {isExpiringSoon
                  ? `⚠ Expira em ${days} dias (${fmtDate(licStatus.expires_at)})`
                  : `Válida até ${fmtDate(licStatus.expires_at)}`}
              </p>
            )}
          </div>
          <span
            className="text-[10px] font-mono px-2 py-0.5 rounded"
            style={{ background: 'rgba(34,197,94,0.1)', color: '#22c55e', border: '1px solid rgba(34,197,94,0.2)' }}
          >
            {licStatus.license_key}
          </span>
        </div>
      ) : (
        <div
          className="flex items-center gap-3 px-4 py-3 rounded-xl"
          style={{ background: '#ef44440d', border: '1px solid #ef444428' }}
        >
          <Shield size={16} style={{ color: '#ef4444' }} />
          <p className="text-sm font-medium text-t1">Licença não ativa</p>
        </div>
      )}

      {/* Stats */}
      {summary && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard icon={Shield}   label="Licenças Ativas"    value={summary.total_active.toString()} color="#3b82f6" />
            <StatCard icon={Camera}   label="Câmeras Licenciadas" value={summary.licenses.filter(l => l.camera_id).length.toString()} color="#22c55e" />
            <StatCard icon={Cpu}      label="Com Analytics/IA"   value={summary.licenses.filter(l => l.has_analytics).length.toString()} color="#8b5cf6" />
            <StatCard icon={Database} label="Câmeras Máximas"    value={licStatus?.max_cameras?.toString() ?? '∞'} color="#f59e0b" />
          </div>

          <div className="card p-4 space-y-3">
            <p className="text-xs font-semibold text-t2 uppercase tracking-wide">Uso de Licenças</p>
            <UsageBar
              value={summary.licenses.filter(l => l.camera_id).length}
              limit={licStatus?.max_cameras ?? null}
              label="Câmeras em uso"
            />
            {Object.entries(summary.by_type).map(([type, count]) => (
              <UsageBar key={type} value={count} limit={null} label={type} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// ── Tab: Storage por Câmera ───────────────────────────────────────────────────

function StorageTab({ cameras }: { cameras: CameraType[] }) {
  const [storageData, setStorageData] = useState<CameraStorage[]>([])
  const [loading, setLoading]         = useState(true)
  const [sortBy, setSortBy]           = useState<'storage' | 'name'>('storage')

  useEffect(() => {
    const fetchStorage = async () => {
      setLoading(true)
      try {
        const results = await Promise.all(
          cameras.map(async (cam) => {
            try {
              const { data } = await api.get(`/recordings?camera_id=${cam.id}&page_size=1`)
              const total = data.total ?? 0
              const totalMb = total * 60 * 4 // estimativa: 60s × 4 MB/seg = 240 MB por segmento
              return {
                camera_id: cam.id,
                camera_name: cam.name,
                segment_count: total,
                total_size_mb: totalMb,
              } as CameraStorage
            } catch {
              return {
                camera_id: cam.id,
                camera_name: cam.name,
                segment_count: 0,
                total_size_mb: 0,
              } as CameraStorage
            }
          })
        )
        setStorageData(results)
      } finally {
        setLoading(false)
      }
    }
    if (cameras.length > 0) fetchStorage()
    else setLoading(false)
  }, [cameras])

  const sorted = [...storageData].sort((a, b) =>
    sortBy === 'storage'
      ? b.total_size_mb - a.total_size_mb
      : a.camera_name.localeCompare(b.camera_name)
  )

  const totalMb = storageData.reduce((acc, c) => acc + c.total_size_mb, 0)
  const maxMb   = Math.max(...storageData.map(c => c.total_size_mb), 1)

  if (loading) return <PageSpinner />

  return (
    <div className="space-y-4">
      {/* Total */}
      <div className="grid grid-cols-2 gap-3">
        <StatCard icon={HardDrive} label="Storage Total Estimado" value={fmtStorage(totalMb)} color="#3b82f6" />
        <StatCard icon={Camera}    label="Câmeras Monitoradas"    value={cameras.length.toString()} color="#22c55e" />
      </div>

      {/* Sort control */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-t3">Ordenar:</span>
        {(['storage', 'name'] as const).map((s) => (
          <button
            key={s}
            onClick={() => setSortBy(s)}
            className="text-xs px-2.5 py-1 rounded-lg transition-all"
            style={{
              background: sortBy === s ? 'rgba(59,130,246,0.15)' : 'var(--elevated)',
              border: `1px solid ${sortBy === s ? 'rgba(59,130,246,0.4)' : 'var(--border)'}`,
              color: sortBy === s ? '#60a5fa' : 'var(--text-3)',
            }}
          >
            {s === 'storage' ? 'Storage ↓' : 'Nome A–Z'}
          </button>
        ))}
      </div>

      {/* Camera list */}
      <div className="card overflow-hidden">
        <div
          className="grid px-4 py-2 text-[10px] font-medium uppercase tracking-wide text-t3"
          style={{
            gridTemplateColumns: '1fr 80px 120px',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <span>Câmera</span>
          <span className="text-right">Segmentos</span>
          <span className="text-right">Storage Est.</span>
        </div>
        {sorted.length === 0 ? (
          <div className="py-10 text-center text-sm text-t3">Nenhuma câmera</div>
        ) : (
          sorted.map((cam) => {
            const pct = maxMb > 0 ? (cam.total_size_mb / maxMb) * 100 : 0
            return (
              <div
                key={cam.camera_id}
                className="px-4 py-3 hover:bg-elevated transition-colors"
                style={{ borderBottom: '1px solid var(--border)' }}
              >
                <div
                  className="grid items-center gap-2 mb-1.5"
                  style={{ gridTemplateColumns: '1fr 80px 120px' }}
                >
                  <span className="text-xs text-t1 truncate font-medium">{cam.camera_name}</span>
                  <span className="text-xs text-t3 tabular-nums text-right">{cam.segment_count}</span>
                  <span className="text-xs text-t2 tabular-nums text-right font-medium">
                    {fmtStorage(cam.total_size_mb)}
                  </span>
                </div>
                <div className="h-1 rounded-full" style={{ background: 'var(--elevated)' }}>
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${pct}%`,
                      background: pct > 70 ? '#f59e0b' : '#3b82f6',
                    }}
                  />
                </div>
              </div>
            )
          })
        )}
      </div>

      <p className="text-[10px] text-t3 text-center">
        * Estimativa baseada em segmentos de 60s a ~4 MB/s. Uso real pode variar.
      </p>
    </div>
  )
}

// ── Tab: Relatório de Uso ─────────────────────────────────────────────────────

function UsageReportTab({ cameras, summary }: { cameras: CameraType[]; summary: LicenseSummary | null }) {
  const total = cameras.length
  const licensed = summary?.licenses.filter(l => l.camera_id).length ?? 0
  const analytics = summary?.licenses.filter(l => l.has_analytics).length ?? 0

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <StatCard icon={Camera}   label="Câmeras Totais"    value={total.toString()}     color="#3b82f6" />
        <StatCard icon={Shield}   label="Câmeras Licenciadas" value={licensed.toString()} color="#22c55e" />
        <StatCard icon={Cpu}      label="Com Analytics"    value={analytics.toString()}  color="#8b5cf6" />
      </div>

      {/* Per-camera analytics */}
      <div className="card overflow-hidden">
        <div
          className="px-4 py-3"
          style={{ borderBottom: '1px solid var(--border)' }}
        >
          <p className="text-xs font-semibold text-t2">Câmeras e Recursos</p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs min-w-[500px]">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Câmera', 'Status', 'Licença', 'Analytics', 'Localização'].map((h) => (
                  <th key={h} className="px-4 py-2.5 text-left text-t3 font-medium">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {cameras.map((cam) => {
                const lic = summary?.licenses.find(l => l.camera_id === cam.id)
                return (
                  <tr
                    key={cam.id}
                    className="hover:bg-elevated transition-colors"
                    style={{ borderBottom: '1px solid var(--border)' }}
                  >
                    <td className="px-4 py-2.5 text-t1 font-medium">{cam.name}</td>
                    <td className="px-4 py-2.5">
                      <span
                        className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded-full"
                        style={{
                          background: cam.is_online ? '#22c55e18' : '#52525b18',
                          color: cam.is_online ? '#22c55e' : '#71717a',
                          border: `1px solid ${cam.is_online ? '#22c55e28' : '#52525b28'}`,
                        }}
                      >
                        <span
                          className="w-1.5 h-1.5 rounded-full"
                          style={{ background: cam.is_online ? '#22c55e' : '#52525b' }}
                        />
                        {cam.is_online ? 'Online' : 'Offline'}
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      {lic ? (
                        <span className="text-[10px] text-green-400">{lic.type}</span>
                      ) : (
                        <span className="text-[10px] text-t3">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-t3">
                      {lic?.has_analytics ? (
                        <span className="text-[10px] text-purple-400">Ativo</span>
                      ) : '—'}
                    </td>
                    <td className="px-4 py-2.5 text-t3 truncate max-w-[160px]">
                      {cam.location ?? '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Summary note */}
      <div
        className="flex items-start gap-3 px-4 py-3 rounded-xl text-xs"
        style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
      >
        <TrendingUp size={14} className="text-t3 shrink-0 mt-0.5" />
        <p className="text-t3">
          Relatório de uso para referência interna. Câmeras sem licença associada podem
          indicar configuração pendente.
        </p>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

type Tab = 'license' | 'storage' | 'usage'

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: 'license', label: 'Licença',      icon: Shield    },
  { id: 'storage', label: 'Storage',      icon: HardDrive },
  { id: 'usage',   label: 'Uso / Câmeras', icon: BarChart2 },
]

export function BillingPage() {
  const [tab, setTab]           = useState<Tab>('license')
  const [licStatus, setLicStatus] = useState<LicenseStatus | null>(null)
  const [summary, setSummary]   = useState<LicenseSummary | null>(null)
  const [cameras, setCameras]   = useState<CameraType[]>([])
  const [loading, setLoading]   = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [statusRes, summaryRes, camsRes] = await Promise.allSettled([
        api.get<LicenseStatus>('/billing/status'),
        api.get<LicenseSummary>('/licenses'),
        camerasService.list({ page_size: 200 }),
      ])
      if (statusRes.status === 'fulfilled') setLicStatus(statusRes.value.data)
      if (summaryRes.status === 'fulfilled') setSummary(summaryRes.value.data)
      if (camsRes.status === 'fulfilled') setCameras(camsRes.value)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return <PageSpinner />

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold text-t1">Financeiro</p>
          <p className="text-xs text-t3 mt-0.5">Licença, storage e uso de recursos</p>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-t2 hover:text-t1 transition-colors"
          style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
        >
          <RefreshCw size={12} />
          Atualizar
        </button>
      </div>

      {/* Tabs */}
      <div
        className="flex gap-1 p-1 rounded-xl"
        style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
      >
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium transition-all flex-1 justify-center',
              tab === id ? 'text-t1' : 'text-t3 hover:text-t2',
            )}
            style={{
              background: tab === id ? 'var(--surface)' : 'transparent',
              border: `1px solid ${tab === id ? 'var(--border)' : 'transparent'}`,
            }}
          >
            <Icon size={13} />
            {label}
            {id === 'license' && licStatus?.expires_at && daysUntil(licStatus.expires_at) !== null && daysUntil(licStatus.expires_at)! <= 30 && (
              <ChevronRight size={10} style={{ color: '#f59e0b' }} />
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'license' && <LicenseTab licStatus={licStatus} summary={summary} />}
      {tab === 'storage' && <StorageTab cameras={cameras} />}
      {tab === 'usage'   && <UsageReportTab cameras={cameras} summary={summary} />}
    </div>
  )
}

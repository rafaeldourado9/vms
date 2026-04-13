import { useEffect, useState } from 'react'
import { Shield, Database, Cpu, AlertTriangle } from 'lucide-react'
import { billingService, type LicenseSummary } from '@/services/billing'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import { format } from 'date-fns'

function ProgressBar({ value, limit, label }: { value: number; limit: number | null; label: string }) {
  const pct = limit ? Math.min((value / limit) * 100, 100) : 0
  const color = pct >= 90 ? '#ef4444' : pct >= 70 ? '#f59e0b' : '#22c55e'

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-t2">{label}</span>
        <span className="text-t3 tabular-nums">
          {value} {limit !== null ? `/ ${limit}` : '∞'}
        </span>
      </div>
      <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--elevated)' }}>
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  )
}

const LICENSE_TYPE_LABELS: Record<string, string> = {
  camera_only: 'Câmera Básica',
  camera_storage: 'Câmera + Storage',
  camera_analytics: 'Câmera + IA',
}

export function BillingPage() {
  const [summary, setSummary] = useState<LicenseSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    billingService.getSummary()
      .then(setSummary)
      .catch(() => setSummary(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <PageSpinner />

  if (!summary) {
    return (
      <div className="py-16 text-center text-sm text-t3">
        Não foi possível carregar informações de licenciamento.
      </div>
    )
  }

  const totalCameras = summary.licenses.filter((l) => l.camera_id).length
  const totalAnalytics = summary.licenses.filter((l) => l.has_analytics).length
  const totalStorage = summary.licenses.reduce((acc, l) => acc + (l.storage_gb ?? 0), 0)

  return (
    <div className="space-y-5 animate-fade-in">
      {/* Header */}
      <div>
        <p className="text-sm font-semibold text-t1">Licenças & Consumo</p>
        <p className="text-xs text-t3 mt-0.5">Gerencie licenças por câmera e limites do tenant</p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-3">
        {[
          { icon: Shield, label: 'Licenças Ativas', value: summary.total_active.toString(), color: '#3b82f6' },
          { icon: Database, label: 'Câmeras Licenciadas', value: totalCameras.toString(), color: '#22c55e' },
          { icon: Cpu, label: 'Com IA/Analytics', value: totalAnalytics.toString(), color: '#8b5cf6' },
          { icon: Database, label: 'Storage Extra (GB)', value: totalStorage > 0 ? totalStorage.toString() : '—', color: '#f59e0b' },
        ].map(({ icon: Icon, label, value, color }) => (
          <div key={label} className="card px-4 py-3">
            <div className="flex items-center gap-2 mb-2">
              <Icon size={16} style={{ color }} />
              <p className="text-xs text-t3">{label}</p>
            </div>
            <p className="text-2xl font-bold text-t1 tabular-nums">{value}</p>
          </div>
        ))}
      </div>

      {/* Quota bars */}
      <div className="card p-4 space-y-4">
        <p className="text-sm font-semibold text-t1">Uso de Recursos</p>
        <ProgressBar
          value={totalCameras}
          limit={summary.total_active > 0 ? summary.total_active : null}
          label="Câmeras ativas"
        />
        <ProgressBar
          value={totalAnalytics}
          limit={null}
          label="Câmeras com IA"
        />
        {totalStorage > 0 && (
          <ProgressBar
            value={totalStorage}
            limit={null}
            label="Storage extra (GB)"
          />
        )}
      </div>

      {/* By type breakdown */}
      {Object.keys(summary.by_type).length > 0 && (
        <div className="card p-4">
          <p className="text-sm font-semibold text-t1 mb-3">Licenças por Tipo</p>
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(summary.by_type).map(([type, count]) => (
              <div key={type} className="card p-3 bg-elevated">
                <p className="text-xs text-t3">{LICENSE_TYPE_LABELS[type] ?? type}</p>
                <p className="text-xl font-bold text-t1 tabular-nums">{count}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* License list */}
      <div className="card overflow-hidden">
        <div className="px-4 py-3 border-b text-xs text-t3 font-medium" style={{ borderColor: 'var(--border)' }}>
          Licenças ({summary.licenses.length})
        </div>
        {summary.licenses.length === 0 ? (
          <div className="py-12 text-center text-sm text-t3">
            Nenhuma licença cadastrada
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[600px]">
              <thead>
                <tr className="border-b text-left" style={{ borderColor: 'var(--border)' }}>
                  {['Câmera', 'Tipo', 'Status', 'Storage', 'Analytics', 'Expira em'].map((h) => (
                    <th key={h} className="px-4 py-3 text-xs font-medium text-t3">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {summary.licenses.map((lic) => {
                  const isExpired = lic.status === 'expired'
                  const isExpiringSoon = lic.expires_at
                    ? (new Date(lic.expires_at).getTime() - Date.now()) < 30 * 24 * 60 * 60 * 1000
                    : false

                  return (
                    <tr key={lic.id} className="border-b hover:bg-elevated transition" style={{ borderColor: 'var(--border)' }}>
                      <td className="px-4 py-3 text-xs text-t1 font-mono">
                        {lic.camera_id?.slice(0, 8) ?? 'Avulsa'}
                      </td>
                      <td className="px-4 py-3 text-xs text-t2">
                        {LICENSE_TYPE_LABELS[lic.type] ?? lic.type}
                      </td>
                      <td className="px-4 py-3">
                        <Badge
                          variant={isExpired ? 'danger' : isExpiringSoon ? 'warning' : 'success'}
                          dot
                        >
                          {isExpired ? 'Expirada' : isExpiringSoon ? 'Expira em breve' : 'Ativa'}
                        </Badge>
                      </td>
                      <td className="px-4 py-3 text-xs text-t2 tabular-nums">
                        {lic.storage_gb ? `${lic.storage_gb} GB` : '—'}
                      </td>
                      <td className="px-4 py-3 text-xs text-t2">
                        {lic.has_analytics ? '✅' : '—'}
                      </td>
                      <td className="px-4 py-3 text-xs text-t3 tabular-nums">
                        {lic.expires_at
                          ? format(new Date(lic.expires_at), 'dd/MM/yyyy')
                          : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Warning if near limit */}
      {summary.total_active > 0 && totalCameras >= Math.floor(summary.total_active * 0.8) && (
        <div className="card p-4 flex items-start gap-3" style={{ background: '#f59e0b0d', borderColor: '#f59e0b30' }}>
          <AlertTriangle size={18} className="text-yellow-500 shrink-0 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-t1">Limite de câmeras próximo</p>
            <p className="text-xs text-t3 mt-0.5">
              Você está usando {totalCameras} de {summary.total_active} licenças disponíveis.
              Considere adquirir mais licenças.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

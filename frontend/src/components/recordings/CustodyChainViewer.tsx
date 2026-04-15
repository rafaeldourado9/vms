/**
 * CustodyChainViewer — timeline visual da cadeia de custódia.
 *
 * Mostra cada ação realizada sobre uma gravação:
 * indexação, verificações, downloads, exports forenses.
 */
import { format } from 'date-fns'
import { FileText, Search, Download, ShieldAlert, User } from 'lucide-react'

interface CustodyEntry {
  action: string
  timestamp: string
  actor: string
  user_email?: string
  file_path?: string
  zip_size_bytes?: number
  hmac_signature?: string
}

interface Props {
  entries: CustodyEntry[]
}

const ACTION_ICONS: Record<string, React.ElementType> = {
  'recording.indexed': FileText,
  'recording.integrity_verified': Search,
  'recording.downloaded': Download,
  'recording.exported_forensic': ShieldAlert,
  'recording.clip_created': FileText,
}

const ACTION_LABELS: Record<string, string> = {
  'recording.indexed': 'Gravação indexada',
  'recording.integrity_verified': 'Integridade verificada',
  'recording.downloaded': 'Download realizado',
  'recording.exported_forensic': 'Export forense',
  'recording.clip_created': 'Clipe criado',
}

export function CustodyChainViewer({ entries }: Props) {
  if (entries.length === 0) {
    return (
      <div className="py-8 text-center text-sm text-t3">
        Nenhuma entrada na cadeia de custódia
      </div>
    )
  }

  return (
    <div className="relative space-y-0">
      {/* Linha vertical */}
      <div className="absolute left-4 top-0 bottom-0 w-px bg-border" />

      {entries.map((entry, i) => {
        const Icon = ACTION_ICONS[entry.action] || FileText
        const label = ACTION_LABELS[entry.action] || entry.action
        const isForensic = entry.action.includes('forensic')
        const isCompromised = entry.action.includes('integrity_failed')

        return (
          <div key={i} className="relative flex gap-4 pb-6 pl-10">
            {/* Dot na linha */}
            <div
              className="absolute left-3 w-3 h-3 rounded-full border-2 shrink-0 z-10"
              style={{
                top: 4,
                background: isForensic ? '#ef4444' : isCompromised ? '#f59e0b' : '#22c55e',
                borderColor: 'var(--surface)',
              }}
            />

            {/* Card */}
            <div className="flex-1 card p-3" style={isForensic ? { background: '#ef444408', borderColor: '#ef444430' } : {}}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <Icon size={14} className="text-t2 shrink-0" />
                  <p className="text-sm font-medium text-t1">{label}</p>
                </div>
                <span className="text-xs text-t3 whitespace-nowrap tabular-nums">
                  {format(new Date(entry.timestamp), 'dd/MM/yy HH:mm:ss')}
                </span>
              </div>

              <div className="flex items-center gap-1.5 mt-1.5 text-xs text-t3">
                <User size={11} />
                <span>{entry.user_email || entry.actor}</span>
              </div>

              {entry.file_path && (
                <p className="text-xs text-t3 mt-1 font-mono truncate">
                  {entry.file_path}
                </p>
              )}

              {entry.zip_size_bytes && (
                <p className="text-xs text-t3 mt-0.5">
                  {(entry.zip_size_bytes / (1024 * 1024)).toFixed(1)} MB
                </p>
              )}

              {entry.hmac_signature && (
                <p className="text-xs text-t3 mt-0.5 font-mono">
                  HMAC: {entry.hmac_signature.slice(0, 16)}...
                </p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

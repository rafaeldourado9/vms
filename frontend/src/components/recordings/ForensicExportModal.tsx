/**
 * ForensicExportModal — modal de exportação forense.
 *
 * Gera ZIP com:
 * - recording.mp4
 * - metadata.json
 * - custody_chain.json
 * - integrity_report.txt
 * - checksum.sha256
 */
import { useState } from 'react'
import { FileDown, Loader2, CheckCircle, AlertTriangle } from 'lucide-react'
import { Modal } from '@/components/ui/Modal'
import { recordingsService } from '@/services/recordings'
import toast from 'react-hot-toast'

interface Props {
  open: boolean
  recordingId: string
  recordingLabel?: string
  onClose: () => void
  onExported?: () => void
}

export function ForensicExportModal({ open, recordingId, recordingLabel, onClose, onExported }: Props) {
  const [exporting, setExporting] = useState(false)
  const [exported, setExported] = useState(false)

  const handleExport = async () => {
    setExporting(true)
    try {
      toast.loading('Gerando pacote forense...', { id: 'forensic' })
      const result = await recordingsService.exportForensic(recordingId)
      toast.success(`Pacote forense gerado: ${(result.zip_size_bytes / (1024 * 1024)).toFixed(1)} MB`, { id: 'forensic' })
      setExported(true)
      onExported?.()
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? 'Erro ao gerar export forense', { id: 'forensic' })
    } finally {
      setExporting(false)
    }
  }

  const handleClose = () => {
    setExported(false)
    onClose()
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Export Forense"
      size="md"
      footer={
        exported ? (
          <button className="btn btn-primary w-full" onClick={handleClose}>
            Fechar
          </button>
        ) : (
          <>
            <button className="btn btn-ghost" onClick={handleClose} disabled={exporting}>Cancelar</button>
            <button className="btn btn-primary flex items-center gap-2" onClick={handleExport} disabled={exporting}>
              {exporting ? (
                <><Loader2 size={16} className="animate-spin" /> Gerando...</>
              ) : (
                <><FileDown size={16} /> Gerar Pacote Forense</>
              )}
            </button>
          </>
        )
      }
    >
      <div className="space-y-4">
        {/* Info */}
        <div className="card p-3 bg-elevated text-xs text-t3">
          <p className="font-medium text-t1 mb-1">O pacote contém:</p>
          <ul className="space-y-0.5 list-disc list-inside">
            <li><code className="text-t2">recording.mp4</code> — gravação original</li>
            <li><code className="text-t2">metadata.json</code> — dados + SHA-256</li>
            <li><code className="text-t2">custody_chain.json</code> — cadeia de custódia</li>
            <li><code className="text-t2">integrity_report.txt</code> — relatório de integridade</li>
            <li><code className="text-t2">checksum.sha256</code> — checksum do arquivo</li>
          </ul>
        </div>

        {/* Gravação */}
        {recordingLabel && (
          <div className="text-sm">
            <span className="text-t3">Gravação:</span>{' '}
            <span className="text-t1 font-medium">{recordingLabel}</span>
          </div>
        )}

        {/* Success */}
        {exported && (
          <div className="card p-4 flex items-start gap-3" style={{ background: '#22c55e0d', borderColor: '#22c55e30' }}>
            <CheckCircle size={20} className="text-green-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-t1">Pacote forense gerado com sucesso</p>
              <p className="text-xs text-t3 mt-0.5">
                O arquivo foi salvo no servidor e registrado na cadeia de custódia.
              </p>
            </div>
          </div>
        )}

        {/* Warning */}
        {!exported && (
          <div className="flex items-start gap-2 text-xs text-t3">
            <AlertTriangle size={14} className="text-yellow-500 shrink-0 mt-0.5" />
            <p>
              A exportação será registrada no audit log e na cadeia de custódia da gravação.
            </p>
          </div>
        )}
      </div>
    </Modal>
  )
}

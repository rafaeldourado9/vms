/**
 * IntegrityBadge — indicador visual de integridade SHA-256.
 *
 * Estados:
 * - verified:   ✅ Verde — hash confere
 * - compromised: ❌ Vermelho — hash divergente
 * - pending:    ⏳ Amarelo — ainda não verificado
 */
import { CheckCircle, XCircle, Clock } from 'lucide-react'

interface Props {
  verified: boolean | null  // null = não verificado ainda
  className?: string
}

export function IntegrityBadge({ verified, className }: Props) {
  if (verified === null) {
    return (
      <span className={`inline-flex items-center gap-1 text-xs ${className || ''}`}>
        <Clock size={12} className="text-yellow-500" />
        <span className="text-yellow-500">Não verificado</span>
      </span>
    )
  }

  if (verified) {
    return (
      <span className={`inline-flex items-center gap-1 text-xs ${className || ''}`}>
        <CheckCircle size={12} className="text-green-500" />
        <span className="text-green-500">Íntegro</span>
      </span>
    )
  }

  return (
    <span className={`inline-flex items-center gap-1 text-xs ${className || ''}`}>
      <XCircle size={12} className="text-red-500" />
      <span className="text-red-500">Comprometido</span>
    </span>
  )
}

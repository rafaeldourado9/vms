import { useState, useEffect } from 'react'
import { ArrowRight, Check, Loader2, AlertTriangle, KeyRound } from 'lucide-react'
import { AddCameraWizard } from './AddCameraWizard'
import { api } from '@/services/api'
import toast from 'react-hot-toast'

interface Props {
  onComplete: () => void
}

export function OnboardingWizard({ onComplete }: Props) {
  const [step, setStep] = useState(0)
  const [accentColor, setAccentColor] = useState('#6366f1')
  const [systemName, setSystemName] = useState('VMS')
  const [showAddCamera, setShowAddCamera] = useState(false)
  const [cameraAdded, setCameraAdded] = useState(false)

  // License key state
  const [licenseKey, setLicenseKey] = useState('')
  const [activating, setActivating] = useState(false)
  const [activationError, setActivationError] = useState('')

  useEffect(() => {
    document.documentElement.style.setProperty('--accent', accentColor)
  }, [accentColor])

  // Format license key as user types: VMS-XXXX-XXXX-XXXX-XXXX
  const handleKeyChange = (value: string) => {
    const cleaned = value.toUpperCase().replace(/[^A-F0-9]/g, '')
    let formatted = 'VMS'
    for (let i = 0; i < cleaned.length && i < 16; i++) {
      if (i % 4 === 0 && i > 0) formatted += '-'
      formatted += cleaned[i]
    }
    setLicenseKey(formatted)
    setActivationError('')
  }

  const handleActivate = async () => {
    if (licenseKey.length < 23) {
      setActivationError('License key incompleta')
      return
    }
    setActivating(true)
    setActivationError('')
    try {
      const { data } = await api.post('/api/v1/billing/activate', { license_key: licenseKey })
      toast.success(`Licença ativada! ${data.licenses_created} licenças de câmera criadas.`)
      localStorage.setItem('vms_onboarding_billing_done', '1')
      setStep(2)
    } catch (err: any) {
      const msg = err.response?.data?.detail ?? 'Erro ao ativar licença'
      setActivationError(msg)
      toast.error(msg)
    } finally {
      setActivating(false)
    }
  }

  const COLORS = ['#6366f1', '#3b82f6', '#0ea5e9', '#14b8a6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6']
  const totalSteps = 4

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: 'var(--bg)' }}>
      <div className="w-full max-w-sm space-y-6">

        {/* Step counter */}
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            {Array.from({ length: totalSteps }).map((_, i) => (
              <div key={i} className="h-1 rounded-full transition-all"
                style={{
                  width: i === step ? '24px' : '8px',
                  background: i <= step ? 'var(--accent)' : 'var(--border)',
                }} />
            ))}
          </div>
          <span className="text-xs text-t3 ml-1">{step + 1} / {totalSteps}</span>
        </div>

        {/* ── Passo 0: Welcome ── */}
        {step === 0 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-t1">Bem-vindo ao VMS</h1>
              <p className="text-sm text-t2 mt-1">
                Configure o sistema em poucas etapas.
              </p>
            </div>
            <div className="space-y-2">
              {['Definir identidade', 'Ativar licença', 'Adicionar câmera', 'Dashboard'].map((item, i) => (
                <div key={i} className="flex items-center gap-3 text-sm text-t2">
                  <span className="text-xs font-mono text-t3 w-4">{String(i + 1).padStart(2, '0')}</span>
                  {item}
                </div>
              ))}
            </div>
            <button className="btn btn-primary w-full" onClick={() => setStep(1)}>
              Começar <ArrowRight size={14} className="ml-1" />
            </button>
          </div>
        )}

        {/* ── Passo 1: Identidade ── */}
        {step === 1 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-xl font-bold text-t1">Identidade</h2>
              <p className="text-sm text-t2 mt-1">Nome e cor do sistema.</p>
            </div>
            <div className="space-y-4">
              <div>
                <label className="label">Nome do sistema</label>
                <input className="input" placeholder="VMS — Empresa XYZ" value={systemName}
                  onChange={(e) => setSystemName(e.target.value)} />
              </div>
              <div>
                <label className="label">Cor primária</label>
                <div className="flex gap-2 mt-1.5 flex-wrap">
                  {COLORS.map((c) => (
                    <button key={c} onClick={() => setAccentColor(c)}
                      className="w-6 h-6 rounded-md transition-transform"
                      style={{
                        background: c,
                        outline: accentColor === c ? `2px solid ${c}` : 'none',
                        outlineOffset: '2px',
                      }} />
                  ))}
                  <input type="color" value={accentColor} onChange={(e) => setAccentColor(e.target.value)}
                    className="w-6 h-6 rounded-md cursor-pointer border-0 bg-transparent p-0" />
                </div>
              </div>
            </div>
            <button className="btn btn-primary w-full" onClick={() => setStep(2)}>
              Próximo <ArrowRight size={14} className="ml-1" />
            </button>
          </div>
        )}

        {/* ── Passo 2: Ativar licença (OBRIGATÓRIO) ── */}
        {step === 2 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-xl font-bold text-t1">Ativar Licença</h2>
              <p className="text-sm text-t2 mt-1">
                Insira a license key fornecida para ativar o sistema.
              </p>
            </div>

            <div>
              <label className="label">License Key</label>
              <div className="relative">
                <KeyRound size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-t3" />
                <input
                  className="input pl-9 font-mono text-lg tracking-widest text-center uppercase"
                  placeholder="VMS-XXXX-XXXX-XXXX-XXXX"
                  value={licenseKey}
                  onChange={(e) => handleKeyChange(e.target.value)}
                  maxLength={23}
                  autoFocus
                />
              </div>
              {activationError && (
                <div className="flex items-center gap-2 mt-2 text-xs text-red-400">
                  <AlertTriangle size={13} />
                  {activationError}
                </div>
              )}
              <p className="text-xs text-t3 mt-2">
                Formato: <code className="text-t2">VMS-XXXX-XXXX-XXXX-XXXX</code>
              </p>
            </div>

            <button
              className="btn btn-primary w-full flex items-center justify-center gap-2"
              onClick={handleActivate}
              disabled={licenseKey.length < 23 || activating}
            >
              {activating ? (
                <>
                  <Loader2 size={16} className="animate-spin" /> Ativando...
                </>
              ) : (
                <>
                  <KeyRound size={16} /> Ativar Sistema
                </>
              )}
            </button>

            <button className="btn btn-ghost w-full text-sm" onClick={() => setStep(3)}>
              Ativar depois
            </button>
          </div>
        )}

        {/* ── Passo 3: Primeira câmera ── */}
        {step === 3 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-xl font-bold text-t1">Primeira câmera</h2>
              <p className="text-sm text-t2 mt-1">Conecte o primeiro dispositivo.</p>
            </div>
            {cameraAdded ? (
              <div className="space-y-3">
                <p className="text-sm text-t2 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: 'var(--success)' }} />
                  Câmera adicionada com sucesso.
                </p>
                <button className="btn btn-primary w-full" onClick={() => {
                  localStorage.setItem('vms_onboarding_complete', '1')
                  onComplete()
                }}>
                  Ir para o Dashboard <Check size={14} className="ml-1" />
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <button className="btn btn-primary w-full" onClick={() => setShowAddCamera(true)}>
                  Adicionar câmera
                </button>
                <button className="btn btn-ghost w-full text-sm" onClick={() => {
                  localStorage.setItem('vms_onboarding_complete', '1')
                  onComplete()
                }}>
                  Pular por enquanto
                </button>
              </div>
            )}
          </div>
        )}

      </div>

      <AddCameraWizard
        open={showAddCamera}
        onClose={() => setShowAddCamera(false)}
        onCreated={() => { setShowAddCamera(false); setCameraAdded(true) }}
        defaultProtocol="rtmp_push"
      />
    </div>
  )
}

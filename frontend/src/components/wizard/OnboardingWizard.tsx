import { useState, useEffect } from 'react'
import { ArrowRight } from 'lucide-react'
import { AddCameraWizard } from './AddCameraWizard'

interface Props {
  onComplete: () => void
}

export function OnboardingWizard({ onComplete }: Props) {
  const [step, setStep] = useState(0)
  const [accentColor, setAccentColor] = useState('#6366f1')
  const [systemName, setSystemName] = useState('VMS')
  const [showAddCamera, setShowAddCamera] = useState(false)
  const [cameraAdded, setCameraAdded] = useState(false)

  useEffect(() => {
    document.documentElement.style.setProperty('--accent', accentColor)
  }, [accentColor])

  const COLORS = ['#6366f1', '#3b82f6', '#0ea5e9', '#14b8a6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6']

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: 'var(--bg)' }}>
      <div className="w-full max-w-sm space-y-6">

        {/* Step counter */}
        <div className="flex items-center gap-2">
          <div className="flex gap-1">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-1 rounded-full transition-all"
                style={{
                  width: i === step ? '24px' : '8px',
                  background: i <= step ? 'var(--accent)' : 'var(--border)',
                }} />
            ))}
          </div>
          <span className="text-xs text-t3 ml-1">{step + 1} / 4</span>
        </div>

        {/* ── Passo 0 ── */}
        {step === 0 && (
          <div className="space-y-5">
            <div>
              <h1 className="text-xl font-bold text-t1">Bem-vindo ao VMS</h1>
              <p className="text-sm text-t2 mt-1">
                Configure o sistema em 3 etapas rápidas.
              </p>
            </div>
            <div className="space-y-2">
              {['Definir identidade da instância', 'Adicionar a primeira câmera', 'Acessar o painel'].map((item, i) => (
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

        {/* ── Passo 1 ── */}
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
            <div className="flex gap-2">
              <button className="btn btn-ghost flex-1 text-sm" onClick={() => setStep(2)}>Pular</button>
              <button className="btn btn-primary flex-1 text-sm" onClick={() => setStep(2)}>
                Próximo <ArrowRight size={14} className="ml-1" />
              </button>
            </div>
          </div>
        )}

        {/* ── Passo 2 ── */}
        {step === 2 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-xl font-bold text-t1">Primeira câmera</h2>
              <p className="text-sm text-t2 mt-1">Conecte o primeiro dispositivo de monitoramento.</p>
            </div>
            {cameraAdded ? (
              <div className="space-y-3">
                <p className="text-sm text-t2 flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full shrink-0" style={{ background: 'var(--success)' }} />
                  Câmera adicionada com sucesso.
                </p>
                <button className="btn btn-primary w-full" onClick={() => setStep(3)}>
                  Continuar <ArrowRight size={14} className="ml-1" />
                </button>
              </div>
            ) : (
              <div className="space-y-2">
                <button className="btn btn-primary w-full" onClick={() => setShowAddCamera(true)}>
                  Adicionar câmera
                </button>
                <button className="btn btn-ghost w-full text-sm" onClick={() => setStep(3)}>
                  Configurar depois
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Passo 3 ── */}
        {step === 3 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-xl font-bold text-t1">Pronto</h2>
              <p className="text-sm text-t2 mt-1">O sistema está configurado e operacional.</p>
            </div>
            <button className="btn btn-primary w-full" onClick={() => {
              localStorage.setItem('vms_onboarding_complete', '1')
              onComplete()
            }}>
              Ir para o Dashboard
            </button>
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

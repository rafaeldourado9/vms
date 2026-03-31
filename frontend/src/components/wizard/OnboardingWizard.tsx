import { useState, useEffect, useRef } from 'react'
import clsx from 'clsx'
import { CheckCircle, Copy, Check, ArrowRight, LayoutDashboard, Grid2x2, Film } from 'lucide-react'
import { Spinner } from '@/components/ui/Spinner'
import { AddCameraWizard } from './AddCameraWizard'
import { agentsService as agentsSvc } from '@/services/agents'
import type { Agent } from '@/types'

interface CreatedAgentResult {
  id: string
  name: string
  api_key: string
  last_heartbeat_at: string | null
}

interface Props {
  onComplete: () => void
}

const STEPS = [
  'Bem-vindo',
  'Instância',
  'Agent',
  'Câmera',
  'Stream',
  'Concluído',
]

export function OnboardingWizard({ onComplete }: Props) {
  const [step, setStep] = useState(0)
  const [accentColor, setAccentColor] = useState('#6366f1')
  const [systemName, setSystemName] = useState('VMS')
  const [createdAgent, setCreatedAgent] = useState<CreatedAgentResult | null>(null)
  const [agentOnline, setAgentOnline] = useState(false)
  const [pollInterval, setPollInterval] = useState<ReturnType<typeof setInterval> | null>(null)
  const [copied, setCopied] = useState<string | null>(null)
  const [showAddCamera, setShowAddCamera] = useState(false)
  const [cameraAdded, setCameraAdded] = useState(false)
  const [agentSkipped, setAgentSkipped] = useState(false)
  const confettiRef = useRef<HTMLDivElement>(null)

  // Aplica cor em tempo real
  useEffect(() => {
    document.documentElement.style.setProperty('--accent', accentColor)
  }, [accentColor])

  // Poll agent status
  useEffect(() => {
    if (step !== 2 || !createdAgent || agentOnline) return

    const id = setInterval(async () => {
      try {
        const agents = await agentsSvc.list()
        const now = Date.now()
        const found = agents.find((a: Agent) => {
          if (a.id !== createdAgent.id) return false
          if (!a.last_heartbeat_at) return false
          return now - new Date(a.last_heartbeat_at).getTime() < 90_000
        })
        if (found) {
          setAgentOnline(true)
          clearInterval(id)
        }
      } catch { /* ignora */ }
    }, 3000)

    setPollInterval(id)
    return () => clearInterval(id)
  }, [step, createdAgent, agentOnline])

  // Auto-avança quando agent conecta
  useEffect(() => {
    if (agentOnline && step === 2) {
      setTimeout(() => setStep(3), 800)
    }
  }, [agentOnline, step])

  // Cleanup poll
  useEffect(() => {
    return () => { if (pollInterval) clearInterval(pollInterval) }
  }, [pollInterval])

  async function handleCreateAgent() {
    try {
      const result = await agentsSvc.create(`Agent-${Date.now()}`)
      setCreatedAgent({ id: result.id, name: result.name, api_key: result.api_key, last_heartbeat_at: result.last_heartbeat_at })
    } catch { /* ignora */ }
  }

  // Ao entrar no passo 2, cria agent automaticamente
  useEffect(() => {
    if (step === 2 && !createdAgent) {
      handleCreateAgent()
    }
  }, [step]) // eslint-disable-line

  function copyToClipboard(text: string, key: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key)
      setTimeout(() => setCopied(null), 2000)
    })
  }

  function getDockerCommand() {
    const apiUrl = window.location.origin
    const key = createdAgent?.api_key ?? '<api_key>'
    return `docker run -d --restart unless-stopped \\
  -e VMS_API_KEY=${key} \\
  -e VMS_API_URL=${apiUrl} \\
  --name vms-agent \\
  vms/edge-agent:latest`
  }

  function handleFinish() {
    localStorage.setItem('vms_onboarding_complete', '1')
    onComplete()
  }

  // ─── Confete CSS puro ─────────────────────────────────────────────────────
  useEffect(() => {
    if (step !== 5 || !confettiRef.current) return
    const container = confettiRef.current
    const colors = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#3b82f6', '#ec4899']
    for (let i = 0; i < 60; i++) {
      const el = document.createElement('div')
      el.style.cssText = `
        position:absolute;
        width:${6 + Math.random() * 6}px;
        height:${6 + Math.random() * 6}px;
        background:${colors[Math.floor(Math.random() * colors.length)]};
        border-radius:${Math.random() > 0.5 ? '50%' : '2px'};
        left:${Math.random() * 100}%;
        top:-10px;
        animation:confetti-fall ${1.5 + Math.random() * 2}s ease-in forwards;
        animation-delay:${Math.random() * 0.5}s;
        opacity:0.85;
      `
      container.appendChild(el)
    }
    return () => { while (container.firstChild) container.removeChild(container.firstChild) }
  }, [step])

  // ─── Render ───────────────────────────────────────────────────────────────
  return (
    <>
      <style>{`
        @keyframes confetti-fall {
          0%   { transform: translateY(0) rotate(0deg); opacity: 0.85; }
          100% { transform: translateY(calc(100vh + 20px)) rotate(720deg); opacity: 0; }
        }
      `}</style>

      <div className="fixed inset-0 bg-bg z-50 flex flex-col items-center justify-center p-6 overflow-auto">
        {step === 5 && (
          <div ref={confettiRef} className="fixed inset-0 pointer-events-none overflow-hidden" />
        )}

        <div className="w-full max-w-lg">
          {/* Step indicator */}
          <div className="flex gap-1.5 mb-8 justify-center">
            {STEPS.map((_, i) => (
              <div key={i} className={clsx('h-1.5 rounded-full transition-all',
                i < step ? 'bg-accent w-6' : i === step ? 'bg-accent w-8' : 'bg-border w-3')}
                style={i <= step ? { backgroundColor: 'var(--accent)' } : {}}
              />
            ))}
          </div>

          {/* ─ Passo 0: Bem-vindo ─ */}
          {step === 0 && (
            <div className="card p-8 text-center space-y-6 animate-fade-in">
              <div className="text-5xl">📹</div>
              <div>
                <h1 className="text-2xl font-bold text-t1">Bem-vindo ao VMS</h1>
                <p className="text-t2 mt-2">Vamos configurar seu sistema em poucos minutos.</p>
              </div>
              <div className="text-left space-y-2">
                {['Configurar instância', 'Instalar o Agent na rede', 'Adicionar sua primeira câmera', 'Verificar o stream ao vivo'].map((item, i) => (
                  <div key={i} className="flex items-center gap-3 text-sm text-t2">
                    <div className="w-5 h-5 rounded-full border-2 border-border flex items-center justify-center text-xs text-t3">{i + 1}</div>
                    {item}
                  </div>
                ))}
              </div>
              <button className="btn btn-primary w-full" onClick={() => setStep(1)}>
                Começar <ArrowRight size={16} className="ml-1" />
              </button>
            </div>
          )}

          {/* ─ Passo 1: Instância ─ */}
          {step === 1 && (
            <div className="card p-8 space-y-5 animate-fade-in">
              <h2 className="text-xl font-semibold text-t1">Configurar instância</h2>
              <div>
                <label className="label">Nome do sistema</label>
                <input className="input" placeholder="VMS — Empresa XYZ" value={systemName}
                  onChange={(e) => setSystemName(e.target.value)} />
              </div>
              <div>
                <label className="label">Cor primária</label>
                <div className="flex gap-2 flex-wrap">
                  {['#6366f1', '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6'].map((c) => (
                    <button key={c} title={c}
                      onClick={() => setAccentColor(c)}
                      className={clsx('w-8 h-8 rounded-full transition-transform', accentColor === c && 'scale-125 ring-2 ring-offset-2 ring-white/30')}
                      style={{ background: c }}
                    />
                  ))}
                  <input type="color" value={accentColor} onChange={(e) => setAccentColor(e.target.value)}
                    className="w-8 h-8 rounded-full cursor-pointer border-0 bg-transparent p-0" title="Cor personalizada" />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button className="btn btn-ghost flex-1" onClick={() => setStep(2)}>Pular</button>
                <button className="btn btn-primary flex-1" onClick={() => setStep(2)}>Próximo <ArrowRight size={14} className="ml-1" /></button>
              </div>
            </div>
          )}

          {/* ─ Passo 2: Agent ─ */}
          {step === 2 && (
            <div className="card p-8 space-y-5 animate-fade-in">
              <h2 className="text-xl font-semibold text-t1">Instalar o Agent</h2>
              <p className="text-sm text-t2">O Agent roda na rede onde estão as câmeras e envia os streams para cá.</p>

              {!createdAgent ? (
                <div className="flex justify-center py-4"><Spinner /></div>
              ) : (
                <>
                  <div>
                    <label className="label">1. Sua API Key</label>
                    <div className="flex items-center gap-2 bg-surface rounded-lg border border-border px-3 py-2">
                      <code className="text-sm text-t1 flex-1 overflow-hidden text-ellipsis">{createdAgent.api_key}</code>
                      <button className="shrink-0 p-1 hover:bg-elevated rounded transition" onClick={() => copyToClipboard(createdAgent.api_key, 'apikey')}>
                        {copied === 'apikey' ? <Check size={14} style={{ color: 'var(--success)' }} /> : <Copy size={14} className="text-t3" />}
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="label">2. Execute no servidor local</label>
                    <div className="relative bg-surface rounded-lg border border-border p-3">
                      <pre className="text-xs text-t2 overflow-x-auto whitespace-pre-wrap break-all">{getDockerCommand()}</pre>
                      <button className="absolute top-2 right-2 p-1 hover:bg-elevated rounded transition" onClick={() => copyToClipboard(getDockerCommand(), 'docker')}>
                        {copied === 'docker' ? <Check size={14} style={{ color: 'var(--success)' }} /> : <Copy size={14} className="text-t3" />}
                      </button>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    {agentOnline ? (
                      <><CheckCircle size={16} style={{ color: 'var(--success)' }} /><span className="text-success" style={{ color: 'var(--success)' }}>Agent conectado!</span></>
                    ) : (
                      <><Spinner size="sm" /><span className="text-t3">Aguardando agent conectar...</span></>
                    )}
                  </div>
                </>
              )}

              <div className="flex gap-3 pt-2">
                <button className="btn btn-ghost flex-1" onClick={() => { setAgentSkipped(true); setStep(3) }}>
                  Pular — tenho câmeras RTMP/ONVIF diretas
                </button>
              </div>
            </div>
          )}

          {/* ─ Passo 3: Câmera ─ */}
          {step === 3 && (
            <div className="card p-8 space-y-4 animate-fade-in">
              <h2 className="text-xl font-semibold text-t1">Adicionar primeira câmera</h2>
              {cameraAdded ? (
                <div className="flex flex-col items-center gap-3 py-4">
                  <CheckCircle size={40} style={{ color: 'var(--success)' }} />
                  <p className="text-t1 font-medium">Câmera adicionada!</p>
                  <button className="btn btn-primary w-full" onClick={() => setStep(4)}>
                    Verificar stream <ArrowRight size={14} className="ml-1" />
                  </button>
                </div>
              ) : (
                <>
                  <p className="text-sm text-t2">Adicione sua primeira câmera para começar a monitorar.</p>
                  <button className="btn btn-primary w-full" onClick={() => setShowAddCamera(true)}>
                    + Adicionar câmera
                  </button>
                  <button className="btn btn-ghost w-full" onClick={() => setStep(4)}>Pular por agora</button>
                </>
              )}
            </div>
          )}

          {/* ─ Passo 4: Stream ─ */}
          {step === 4 && (
            <div className="card p-8 space-y-4 animate-fade-in text-center">
              <h2 className="text-xl font-semibold text-t1">Tudo pronto!</h2>
              <p className="text-sm text-t2">Seu VMS está configurado. As câmeras aparecerão no dashboard assim que o agent enviar os streams.</p>
              <div className="flex flex-col gap-2 pt-2">
                <button className="btn btn-primary w-full" onClick={() => setStep(5)}>Concluir configuração</button>
              </div>
            </div>
          )}

          {/* ─ Passo 5: Concluído ─ */}
          {step === 5 && (
            <div className="card p-8 text-center space-y-5 animate-fade-in">
              <div className="text-5xl">🎉</div>
              <h2 className="text-2xl font-bold text-t1">Sistema configurado!</h2>
              <p className="text-t2 text-sm">Seu VMS está pronto. Explore as funcionalidades abaixo.</p>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'Dashboard', href: '/dashboard', Icon: LayoutDashboard },
                  { label: 'Mosaico',   href: '/mosaic',    Icon: Grid2x2 },
                  { label: 'Gravações', href: '/recordings', Icon: Film },
                ].map(({ label, href, Icon }) => (
                  <a key={href} href={href}
                    className="flex flex-col items-center gap-2 p-3 rounded-xl border border-border hover:border-accent transition text-sm text-t2 hover:text-t1"
                  >
                    <Icon size={20} />
                    {label}
                  </a>
                ))}
              </div>
              <button className="btn btn-primary w-full" onClick={handleFinish}>
                Ir para o Dashboard
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Wizard de câmera embutido */}
      <AddCameraWizard
        open={showAddCamera}
        onClose={() => setShowAddCamera(false)}
        onCreated={() => { setShowAddCamera(false); setCameraAdded(true) }}
        defaultProtocol={agentSkipped ? 'rtmp_push' : 'rtsp_pull'}
      />
    </>
  )
}

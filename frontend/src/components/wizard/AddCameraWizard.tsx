import { useState } from 'react'
import clsx from 'clsx'
import {
  Radio, Wifi, Eye, Globe, ArrowRight, ArrowLeft,
  CheckCircle, AlertTriangle, Copy, Check,
} from 'lucide-react'
import { Modal } from '@/components/ui/Modal'
import { Spinner } from '@/components/ui/Spinner'
import { useConnectionTest } from '@/hooks/useConnectionTest'
import { camerasService as camerasSvc } from '@/services/cameras'
import { analyticsService as analyticsSvc } from '@/services/analytics'
import { agentsService as agentsSvc } from '@/services/agents'
import type { Agent } from '@/types'

// ─── Tipos ────────────────────────────────────────────────────────────────────

type Protocol = 'rtsp_pull' | 'rtmp_push' | 'onvif' | 'manual'

interface AnalyticToggle {
  key: string
  label: string
  description: string
  ia_type: string
}

const ANALYTICS: AnalyticToggle[] = [
  { key: 'lpr',       label: 'Reconhec. de Placa',  description: 'Detecta e lê placas veiculares',  ia_type: 'lpr' },
  { key: 'vehicle',   label: 'Tráfego de Veículos', description: 'Conta e classifica veículos',     ia_type: 'vehicle_traffic' },
  { key: 'people',    label: 'Tráfego Humano',      description: 'Conta pessoas na região',         ia_type: 'human_traffic' },
  { key: 'intrusion', label: 'Detecção de Intrusão', description: 'Alerta em zona proibida',        ia_type: 'intrusion' },
]

const PROTOCOL_CARDS = [
  { id: 'rtsp_pull', label: 'RTSP via Agent', desc: 'IP cameras, DVR/NVR na rede local', Icon: Radio },
  { id: 'rtmp_push', label: 'RTMP Push',      desc: 'Câmera envia direto para o VMS',   Icon: Wifi },
  { id: 'onvif',     label: 'ONVIF',          desc: 'Auto-descoberta de stream',         Icon: Eye },
  { id: 'manual',    label: 'URL Manual',     desc: 'RTSP/RTMP url direta (avançado)',   Icon: Globe },
]

// ─── Componente principal ─────────────────────────────────────────────────────

interface AddCameraWizardProps {
  open: boolean
  onClose: () => void
  onCreated: () => void
  defaultProtocol?: Protocol
}

export function AddCameraWizard({ open, onClose, onCreated, defaultProtocol }: AddCameraWizardProps) {
  const [step, setStep] = useState(0)
  const [protocol, setProtocol] = useState<Protocol>(defaultProtocol ?? 'rtsp_pull')
  const [agents, setAgents] = useState<Agent[]>([])
  const [agentsLoaded, setAgentsLoaded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [createdCamera, setCreatedCamera] = useState<{ id: string; rtmp_url?: string; stream_key?: string } | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  // form state
  const [form, setForm] = useState({
    name: '',
    location: '',
    retention_days: 7,
    agent_id: '',
    rtsp_url: '',
    onvif_url: '',
    onvif_username: 'admin',
    onvif_password: '',
    manufacturer: 'generic',
    // manual
    manual_url: '',
  })
  const [enabledAnalytics, setEnabledAnalytics] = useState<Set<string>>(new Set())

  const { result: connTest, testOnvif, reset: resetTest } = useConnectionTest()

  const totalSteps = protocol === 'rtmp_push' ? 5 : 6

  // ─── Handlers ───────────────────────────────────────────────────────────────

  async function loadAgents() {
    if (agentsLoaded) return
    try {
      const list = await agentsSvc.list()
      setAgents(list)
      setAgentsLoaded(true)
      if (list.length > 0 && !form.agent_id) {
        setForm((f) => ({ ...f, agent_id: list[0].id }))
      }
    } catch { /* silencioso */ }
  }

  function handleNext() {
    if (step === 0) loadAgents()
    if (step === 1 && protocol === 'onvif' && connTest.status === 'ok' && connTest.rtsp_url) {
      setForm((f) => ({ ...f, rtsp_url: connTest.rtsp_url! }))
    }
    setStep((s) => s + 1)
  }

  function handleBack() {
    setStep((s) => s - 1)
    resetTest()
  }

  async function handleCreate() {
    setLoading(true)
    try {
      const payload: Parameters<typeof camerasSvc.create>[0] = {
        name: form.name,
        location: form.location || undefined,
        manufacturer: form.manufacturer as 'hikvision' | 'intelbras' | 'dahua' | 'generic',
        retention_days: form.retention_days,
        stream_protocol: protocol === 'manual' ? 'rtsp_pull' : protocol,
        rtsp_url: protocol === 'rtsp_pull' || protocol === 'manual'
          ? (form.rtsp_url || form.manual_url || undefined)
          : protocol === 'onvif' ? (connTest.rtsp_url ?? undefined) : undefined,
        agent_id: (protocol === 'rtsp_pull' || protocol === 'manual') ? (form.agent_id || undefined) : undefined,
        onvif_url: protocol === 'onvif' ? form.onvif_url : undefined,
        onvif_username: protocol === 'onvif' ? form.onvif_username : undefined,
        onvif_password: protocol === 'onvif' ? form.onvif_password : undefined,
      }
      const camera = await camerasSvc.create(payload)

      // Criar ROIs para analytics habilitados
      for (const key of enabledAnalytics) {
        const analytic = ANALYTICS.find((a) => a.key === key)
        if (!analytic) continue
        try {
          await analyticsSvc.createROI({
            camera_id: camera.id,
            name: analytic.label,
            ia_type: analytic.ia_type,
            polygon_points: [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]],
            config: {},
          })
        } catch { /* continua mesmo se ROI falhar */ }
      }

      let rtmpInfo: { rtmp_url?: string; stream_key?: string } = {}
      if (protocol === 'rtmp_push') {
        try {
          const rtmp = await camerasSvc.rtmpConfig(camera.id)
          rtmpInfo = { rtmp_url: rtmp.rtmp_url, stream_key: rtmp.stream_key }
        } catch { /* */ }
      }

      setCreatedCamera({ id: camera.id, ...rtmpInfo })
      setStep(totalSteps - 1)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Erro ao criar câmera'
      alert(msg)
    } finally {
      setLoading(false)
    }
  }

  function copyToClipboard(text: string, key: string) {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(key)
      setTimeout(() => setCopied(null), 2000)
    })
  }

  function handleClose() {
    if (createdCamera) onCreated()
    setStep(0)
    setProtocol(defaultProtocol ?? 'rtsp_pull')
    setCreatedCamera(null)
    setForm({ name: '', location: '', retention_days: 7, agent_id: '', rtsp_url: '', onvif_url: '', onvif_username: 'admin', onvif_password: '', manufacturer: 'generic', manual_url: '' })
    setEnabledAnalytics(new Set())
    resetTest()
    onClose()
  }

  // ─── Passos ─────────────────────────────────────────────────────────────────

  const steps = [
    { label: 'Protocolo' },
    { label: 'Conexão' },
    { label: 'Configuração' },
    { label: 'Analíticos' },
    { label: 'Revisão' },
    ...(protocol === 'rtmp_push' ? [] : []),
  ]

  const canNext = (): boolean => {
    if (step === 0) return true
    if (step === 1) {
      if (protocol === 'rtsp_pull') return !!form.rtsp_url && !!form.agent_id
      if (protocol === 'onvif') return !!form.onvif_url && !!form.onvif_password
      if (protocol === 'rtmp_push') return true
      if (protocol === 'manual') return !!form.manual_url
    }
    if (step === 2) return !!form.name
    return true
  }

  const isReviewStep = step === steps.length - 2
  const isDoneStep = createdCamera !== null && step === totalSteps - 1

  // ─── Render ─────────────────────────────────────────────────────────────────

  return (
    <Modal open={open} onClose={handleClose} title="Adicionar Câmera" size="lg"
      footer={
        isDoneStep ? (
          <button className="btn btn-primary" onClick={handleClose}>Ir para Câmeras</button>
        ) : (
          <div className="flex justify-between w-full">
            <button className="btn btn-ghost" onClick={step === 0 ? handleClose : handleBack} disabled={loading}>
              {step === 0 ? 'Cancelar' : <><ArrowLeft size={14} className="mr-1" />Voltar</>}
            </button>
            {isReviewStep ? (
              <button className="btn btn-primary" onClick={handleCreate} disabled={loading}>
                {loading ? <Spinner size="sm" /> : <><CheckCircle size={14} className="mr-1" />Criar Câmera</>}
              </button>
            ) : (
              <button className="btn btn-primary" onClick={handleNext} disabled={!canNext()}>
                Próximo <ArrowRight size={14} className="ml-1" />
              </button>
            )}
          </div>
        )
      }
    >
      {/* Progress bar */}
      {!isDoneStep && (
        <div className="flex gap-1 mb-6">
          {steps.map((s, i) => (
            <div key={i} className="flex-1 flex flex-col gap-1">
              <div className={clsx('h-1 rounded-full transition-all', i <= step ? 'bg-accent' : 'bg-border')} />
              <span className={clsx('text-xs text-center', i === step ? 'text-t1' : 'text-t3')}>{s.label}</span>
            </div>
          ))}
        </div>
      )}

      {/* Passo 0 — Protocolo */}
      {step === 0 && (
        <div className="grid grid-cols-2 gap-3">
          {PROTOCOL_CARDS.map(({ id, label, desc, Icon }) => (
            <button
              key={id}
              onClick={() => setProtocol(id as Protocol)}
              className={clsx(
                'p-4 rounded-xl border text-left transition flex items-start gap-3',
                protocol === id ? 'border-accent bg-surface' : 'border-border hover:border-t3',
              )}
              style={protocol === id ? { borderColor: 'var(--accent)' } : {}}
            >
              <Icon size={20} className={protocol === id ? 'text-accent' : 'text-t3'} style={protocol === id ? { color: 'var(--accent)' } : {}} />
              <div>
                <div className="text-sm font-medium text-t1">{label}</div>
                <div className="text-xs text-t3 mt-0.5">{desc}</div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Passo 1 — Conexão */}
      {step === 1 && (
        <div className="space-y-4">
          {protocol === 'rtsp_pull' && (
            <>
              <div>
                <label className="label">Agent *</label>
                {agents.length === 0 ? (
                  <p className="text-xs text-warning">Nenhum agent online. <a href="/agents" className="underline">Configurar agents →</a></p>
                ) : (
                  <select className="input" value={form.agent_id} onChange={(e) => setForm((f) => ({ ...f, agent_id: e.target.value }))}>
                    <option value="">Selecionar agent...</option>
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>{a.name} ({a.is_active ? 'ativo' : 'inativo'})</option>
                    ))}
                  </select>
                )}
              </div>
              <div>
                <label className="label">URL RTSP *</label>
                <input className="input" placeholder="rtsp://192.168.1.100:554/stream" value={form.rtsp_url}
                  onChange={(e) => setForm((f) => ({ ...f, rtsp_url: e.target.value }))} />
                <p className="text-xs text-t3 mt-1">Formato: rtsp://usuario:senha@ip:porta/caminho</p>
              </div>
            </>
          )}

          {protocol === 'rtmp_push' && (
            <div className="rounded-xl border border-border p-4 bg-surface text-sm text-t2 space-y-2">
              <p className="text-t1 font-medium">Câmera enviará o stream para o VMS</p>
              <p>Após criar a câmera, você receberá a URL RTMP e a Stream Key para configurar na câmera.</p>
              <p className="text-t3 text-xs">Nenhuma configuração adicional necessária aqui.</p>
            </div>
          )}

          {protocol === 'onvif' && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">IP da câmera *</label>
                  <input className="input" placeholder="192.168.1.100" value={form.onvif_url.replace(/^http:\/\//, '').split(':')[0]}
                    onChange={(e) => setForm((f) => ({ ...f, onvif_url: `http://${e.target.value}:80/onvif/device_service` }))} />
                </div>
                <div>
                  <label className="label">Usuário</label>
                  <input className="input" placeholder="admin" value={form.onvif_username}
                    onChange={(e) => setForm((f) => ({ ...f, onvif_username: e.target.value }))} />
                </div>
              </div>
              <div>
                <label className="label">Senha</label>
                <input className="input" type="password" placeholder="••••••" value={form.onvif_password}
                  onChange={(e) => setForm((f) => ({ ...f, onvif_password: e.target.value }))} />
              </div>
              <button
                className="btn btn-ghost w-full"
                onClick={() => testOnvif(form.onvif_url, form.onvif_username, form.onvif_password)}
                disabled={!form.onvif_url || !form.onvif_password || connTest.status === 'loading'}
              >
                {connTest.status === 'loading' ? <Spinner size="sm" /> : <Eye size={14} className="mr-1" />}
                Descobrir stream
              </button>
              {connTest.status === 'ok' && (
                <div className="rounded-xl border border-success/30 bg-surface p-3 text-sm space-y-1">
                  <div className="flex items-center gap-2 text-success"><CheckCircle size={14} />Câmera detectada</div>
                  {connTest.manufacturer && <div className="text-t2">Fabricante: {connTest.manufacturer} {connTest.model}</div>}
                  {connTest.rtsp_url && <div className="text-t3 text-xs break-all">Stream: {connTest.rtsp_url}</div>}
                </div>
              )}
              {connTest.status === 'error' && (
                <div className="rounded-xl border border-danger/30 bg-surface p-3 text-sm">
                  <div className="flex items-center gap-2 text-danger"><AlertTriangle size={14} />{connTest.error}</div>
                </div>
              )}
            </>
          )}

          {protocol === 'manual' && (
            <>
              <div>
                <label className="label">Agent (opcional)</label>
                <select className="input" value={form.agent_id} onChange={(e) => setForm((f) => ({ ...f, agent_id: e.target.value }))}>
                  <option value="">Sem agent (stream direto)</option>
                  {agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
                </select>
              </div>
              <div>
                <label className="label">URL *</label>
                <input className="input" placeholder="rtsp://... ou rtmp://..." value={form.manual_url}
                  onChange={(e) => setForm((f) => ({ ...f, manual_url: e.target.value }))} />
              </div>
            </>
          )}
        </div>
      )}

      {/* Passo 2 — Configuração */}
      {step === 2 && (
        <div className="space-y-4">
          <div>
            <label className="label">Nome *</label>
            <input className="input" placeholder="Ex: Câmera Entrada Principal" value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} autoFocus />
          </div>
          <div>
            <label className="label">Localização</label>
            <input className="input" placeholder="Ex: Portaria Norte — Bloco A" value={form.location}
              onChange={(e) => setForm((f) => ({ ...f, location: e.target.value }))} />
          </div>
          <div>
            <label className="label">Fabricante</label>
            <select className="input" value={form.manufacturer} onChange={(e) => setForm((f) => ({ ...f, manufacturer: e.target.value }))}>
              <option value="generic">Genérico</option>
              <option value="hikvision">Hikvision</option>
              <option value="intelbras">Intelbras</option>
              <option value="dahua">Dahua</option>
            </select>
          </div>
          <div>
            <label className="label">Retenção de gravações</label>
            <div className="flex gap-2">
              {[7, 15, 30].map((d) => (
                <button key={d}
                  onClick={() => setForm((f) => ({ ...f, retention_days: d }))}
                  className={clsx('px-4 py-2 rounded-lg text-sm border transition',
                    form.retention_days === d ? 'text-white border-accent' : 'text-t2 border-border hover:border-t3')}
                  style={form.retention_days === d ? { background: 'var(--accent)', borderColor: 'var(--accent)' } : {}}
                >
                  {d} dias
                </button>
              ))}
              <input type="number" className="input w-24 text-sm" min={1} max={90} value={form.retention_days}
                onChange={(e) => setForm((f) => ({ ...f, retention_days: parseInt(e.target.value, 10) || 7 }))} />
            </div>
          </div>
        </div>
      )}

      {/* Passo 3 — Analíticos */}
      {step === 3 && (
        <div className="space-y-3">
          <p className="text-sm text-t2 mb-4">Habilite os analíticos de IA. Cada um cria uma ROI padrão editável depois.</p>
          <div className="grid grid-cols-2 gap-3">
            {ANALYTICS.map(({ key, label, description }) => {
              const enabled = enabledAnalytics.has(key)
              return (
                <button key={key}
                  onClick={() => setEnabledAnalytics((s) => { const n = new Set(s); enabled ? n.delete(key) : n.add(key); return n })}
                  className={clsx('p-4 rounded-xl border text-left transition',
                    enabled ? 'border-accent bg-surface' : 'border-border hover:border-t3')}
                  style={enabled ? { borderColor: 'var(--accent)' } : {}}
                >
                  <div className="flex justify-between items-start">
                    <div className="text-sm font-medium text-t1">{label}</div>
                    <div className={clsx('w-9 h-5 rounded-full transition-colors flex items-center px-0.5',
                      enabled ? 'bg-accent' : 'bg-border')}
                      style={enabled ? { backgroundColor: 'var(--accent)' } : {}}
                    >
                      <div className={clsx('w-4 h-4 rounded-full bg-white shadow transition-transform', enabled ? 'translate-x-4' : 'translate-x-0')} />
                    </div>
                  </div>
                  <div className="text-xs text-t3 mt-1">{description}</div>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Passo 4 — Revisão */}
      {step === 4 && !isDoneStep && (
        <div className="space-y-3">
          <p className="text-sm text-t2 mb-2">Revise antes de criar:</p>
          <div className="rounded-xl border border-border divide-y divide-border">
            {[
              ['Nome', form.name],
              ['Localização', form.location || '—'],
              ['Protocolo', protocol],
              ['Fabricante', form.manufacturer],
              ['Retenção', `${form.retention_days} dias`],
              ['Analíticos', enabledAnalytics.size > 0 ? [...enabledAnalytics].join(', ') : 'Nenhum'],
            ].map(([k, v]) => (
              <div key={k} className="flex px-4 py-2.5">
                <span className="text-sm text-t3 w-32 shrink-0">{k}</span>
                <span className="text-sm text-t1">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Passo final — Criado (RTMP key) */}
      {isDoneStep && createdCamera && (
        <div className="space-y-4 text-center">
          <div className="flex justify-center">
            <CheckCircle size={48} className="text-success" style={{ color: 'var(--success)' }} />
          </div>
          <p className="text-t1 font-semibold text-lg">Câmera criada com sucesso!</p>

          {protocol === 'rtmp_push' && createdCamera.rtmp_url && (
            <div className="text-left space-y-3">
              <p className="text-sm text-t2">Configure na câmera as seguintes informações:</p>
              <div className="space-y-2">
                {[
                  { label: 'RTMP URL', value: createdCamera.rtmp_url, key: 'url' },
                  { label: 'Stream Key', value: createdCamera.stream_key ?? '', key: 'key' },
                ].map(({ label, value, key }) => (
                  <div key={key} className="rounded-xl border border-border bg-surface p-3">
                    <div className="text-xs text-t3 mb-1">{label}</div>
                    <div className="flex items-center justify-between gap-2">
                      <code className="text-sm text-t1 break-all">{value}</code>
                      <button className="shrink-0 p-1.5 rounded hover:bg-elevated transition" onClick={() => copyToClipboard(value, key)}>
                        {copied === key ? <Check size={14} className="text-success" style={{ color: 'var(--success)' }} /> : <Copy size={14} className="text-t3" />}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              <p className="text-xs text-warning flex gap-1"><AlertTriangle size={12} />A Stream Key não será exibida novamente.</p>
            </div>
          )}

          {protocol !== 'rtmp_push' && (
            <p className="text-sm text-t2">O stream estará disponível assim que a câmera se conectar ao agent.</p>
          )}
        </div>
      )}
    </Modal>
  )
}

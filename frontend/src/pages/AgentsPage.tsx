import { useEffect, useState } from 'react'
import { Plus, Server, Copy, Check, Clock } from 'lucide-react'
import { format } from 'date-fns'
import { agentsService } from '@/services/agents'
import { PageSpinner } from '@/components/ui/Spinner'
import { Badge } from '@/components/ui/Badge'
import { Modal } from '@/components/ui/Modal'
import { usePermission } from '@/hooks/usePermission'
import toast from 'react-hot-toast'
import type { Agent } from '@/types'

interface NewAgentResult {
  id: string
  name: string
  api_key: string
}

export function AgentsPage() {
  const { isAdmin } = usePermission()
  const [agents, setAgents]         = useState<Agent[]>([])
  const [loading, setLoading]       = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [agentName, setAgentName]   = useState('')
  const [creating, setCreating]     = useState(false)
  const [newAgent, setNewAgent]     = useState<NewAgentResult | null>(null)
  const [copied, setCopied]         = useState(false)

  const load = () => {
    agentsService.list().then(setAgents).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleCreate = async () => {
    if (!agentName.trim()) return
    setCreating(true)
    try {
      const result = await agentsService.create(agentName.trim())
      setNewAgent({ id: result.id, name: result.name, api_key: result.api_key })
      setAgentName('')
      setShowCreate(false)
      load()
    } catch { toast.error('Erro ao criar agent') } finally {
      setCreating(false)
    }
  }

  const copyKey = async () => {
    if (!newAgent) return
    await navigator.clipboard.writeText(newAgent.api_key)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const isOnline = (agent: Agent) => {
    if (!agent.last_heartbeat_at) return false
    const diff = Date.now() - new Date(agent.last_heartbeat_at).getTime()
    return diff < 120_000 // 2 minutos
  }

  if (loading) return <PageSpinner />

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-t2">
            Agents são processos que rodam na rede do cliente e enviam streams RTSP para o servidor.
          </p>
        </div>
        {isAdmin && (
          <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
            <Plus size={16} />Novo Agent
          </button>
        )}
      </div>

      {/* Agents list */}
      <div className="space-y-3">
        {agents.map((agent) => (
          <div key={agent.id} className="card p-4 flex items-center gap-4">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: 'var(--elevated)' }}
            >
              <Server size={20} className="text-t2" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-t1">{agent.name}</p>
                <Badge variant={isOnline(agent) ? 'success' : 'danger'} dot>
                  {isOnline(agent) ? 'Online' : 'Offline'}
                </Badge>
                {!agent.is_active && <Badge variant="warning">Desativado</Badge>}
              </div>
              <p className="text-xs text-t3 font-mono mt-0.5">{agent.id}</p>
            </div>
            <div className="flex items-center gap-2 text-xs text-t3 shrink-0">
              <Clock size={13} />
              {agent.last_heartbeat_at
                ? format(new Date(agent.last_heartbeat_at), 'dd/MM HH:mm')
                : 'Nunca conectado'}
            </div>
          </div>
        ))}
        {agents.length === 0 && (
          <div className="card p-16 text-center">
            <Server size={32} className="text-t3 mx-auto mb-3" />
            <p className="text-t3 text-sm">Nenhum agent configurado</p>
            <p className="text-t3 text-xs mt-1">Crie um agent para conectar câmeras RTSP à rede do cliente</p>
          </div>
        )}
      </div>

      {/* Create modal */}
      <Modal
        open={showCreate}
        onClose={() => setShowCreate(false)}
        title="Novo Agent"
        size="sm"
        footer={
          <>
            <button className="btn btn-ghost" onClick={() => setShowCreate(false)}>Cancelar</button>
            <button className="btn btn-primary" onClick={handleCreate} disabled={creating || !agentName.trim()}>
              {creating ? 'Criando...' : 'Criar'}
            </button>
          </>
        }
      >
        <div>
          <label className="label">Nome do Agent</label>
          <input
            className="input"
            placeholder="Ex: Sede Principal"
            value={agentName}
            onChange={(e) => setAgentName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
          />
          <p className="text-xs text-t3 mt-2">
            Escolha um nome que identifique a localidade onde o agent será instalado.
          </p>
        </div>
      </Modal>

      {/* API Key reveal modal */}
      <Modal
        open={!!newAgent}
        onClose={() => setNewAgent(null)}
        title="Agent Criado!"
        size="md"
        footer={
          <button className="btn btn-primary" onClick={() => setNewAgent(null)}>Entendido</button>
        }
      >
        {newAgent && (
          <div className="space-y-4">
            <div
              className="p-3 rounded-lg"
              style={{ background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.2)' }}
            >
              <p className="text-xs text-green-400">
                Agent <strong>{newAgent.name}</strong> criado com sucesso.
              </p>
            </div>

            <div>
              <p className="text-sm font-semibold text-t1 mb-1">API Key</p>
              <p className="text-xs text-danger mb-3">
                Esta chave será exibida apenas uma vez. Copie e armazene com segurança.
              </p>
              <div
                className="flex items-center gap-2 p-3 rounded-lg font-mono text-xs"
                style={{ background: 'var(--elevated)', border: '1px solid var(--border)' }}
              >
                <code className="flex-1 break-all text-t1">{newAgent.api_key}</code>
                <button
                  className="btn btn-ghost w-8 h-8 p-0 shrink-0"
                  onClick={copyKey}
                  title="Copiar"
                >
                  {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
                </button>
              </div>
            </div>

            <div className="p-3 rounded-lg" style={{ background: 'var(--elevated)' }}>
              <p className="text-xs text-t2 font-semibold mb-1">Como usar:</p>
              <p className="text-xs text-t3">
                Configure o edge agent com esta chave. O agent irá se autenticar e receber as configurações das câmeras automaticamente.
              </p>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

import { api } from './api'
import type { Agent } from '@/types'

interface CreateAgentResponse {
  id: string
  tenant_id: string
  name: string
  is_active: boolean
  last_heartbeat_at: string | null
  created_at: string
  api_key: string
}

export const agentsService = {
  async list(): Promise<Agent[]> {
    const res = await api.get<Agent[]>('/agents')
    return res.data
  },

  async create(name: string): Promise<CreateAgentResponse> {
    const res = await api.post<CreateAgentResponse>('/agents', { name })
    return res.data
  },
}

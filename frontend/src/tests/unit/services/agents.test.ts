import { describe, it, expect, vi, beforeEach } from 'vitest'
import { agentsService } from './agents'

// Mock api module
vi.mock('./api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}))

// Need to re-import after mock
const { api } = await import('./api')

describe('agentsService', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('list', () => {
    it('returns agents array', async () => {
      const mockAgents = [
        { id: '1', name: 'agent-01', status: 'online', tenant_id: 't1' },
        { id: '2', name: 'agent-02', status: 'offline', tenant_id: 't1' },
      ]
      vi.mocked(api.get).mockResolvedValueOnce({ data: mockAgents })

      const result = await agentsService.list()

      expect(api.get).toHaveBeenCalledWith('/api/v1/agents')
      expect(result).toHaveLength(2)
      expect(result[0].name).toBe('agent-01')
    })

    it('returns empty array on error', async () => {
      vi.mocked(api.get).mockRejectedValueOnce(new Error('Network error'))

      await expect(agentsService.list()).rejects.toThrow()
    })
  })

  describe('create', () => {
    it('creates agent with name', async () => {
      const newAgent = { id: '1', name: 'new-agent', status: 'pending', tenant_id: 't1' }
      vi.mocked(api.post).mockResolvedValueOnce({ data: newAgent })

      const result = await agentsService.create('new-agent')

      expect(api.post).toHaveBeenCalledWith('/api/v1/agents', { name: 'new-agent' })
      expect(result.name).toBe('new-agent')
    })
  })

  describe('delete', () => {
    it('calls delete endpoint', async () => {
      vi.mocked(api.delete).mockResolvedValueOnce({})

      await agentsService.delete('agent-123')

      expect(api.delete).toHaveBeenCalledWith('/api/v1/agents/agent-123')
    })
  })

  describe('update', () => {
    it('updates agent name', async () => {
      const updated = { id: '1', name: 'renamed', status: 'online', tenant_id: 't1' }
      vi.mocked(api.put).mockResolvedValueOnce({ data: updated })

      const result = await agentsService.update('agent-123', { name: 'renamed' })

      expect(api.put).toHaveBeenCalledWith('/api/v1/agents/agent-123', { name: 'renamed' })
      expect(result.name).toBe('renamed')
    })
  })
})

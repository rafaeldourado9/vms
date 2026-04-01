import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'

// Mock axios to avoid actual HTTP calls
vi.mock('axios', async () => {
  const actual = await vi.importActual<typeof axios>('axios')
  return {
    default: {
      ...actual.default,
      create: vi.fn(() => ({
        interceptors: {
          request: { use: vi.fn() },
          response: { use: vi.fn() },
        },
      })),
      post: vi.fn(),
    },
  }
})

// Mock authStore
const mockLogout = vi.fn()
const mockSetTokens = vi.fn()
vi.mock('@/store/authStore', () => ({
  useAuthStore: {
    getState: () => ({
      tokens: { access_token: 'access-token', refresh_token: 'refresh-token' },
      logout: mockLogout,
      setTokens: mockSetTokens,
    }),
    subscribe: vi.fn(),
  },
}))

describe('api service', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('creates axios instance with baseURL /api/v1', async () => {
    const { api } = await import('@/services/api')
    // The api instance is created with create() which we mocked
    expect(axios.create).toHaveBeenCalledWith(
      expect.objectContaining({ baseURL: '/api/v1' }),
    )
  })

  it('registers request and response interceptors', async () => {
    const { api } = await import('@/services/api')
    expect(api.interceptors.request.use).toHaveBeenCalled()
    expect(api.interceptors.response.use).toHaveBeenCalled()
  })
})

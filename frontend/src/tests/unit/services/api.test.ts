import { describe, it, expect, vi, beforeEach } from 'vitest'

describe('api service', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
  })

  it('creates axios instance with baseURL /api/v1', async () => {
    const axiosMod = await vi.importMock('axios') as { default: { create: ReturnType<typeof vi.fn> } }
    // Use dynamic import so the module is re-evaluated with fresh mocks
    vi.doMock('axios', () => ({
      default: {
        create: vi.fn(() => ({
          interceptors: {
            request: { use: vi.fn() },
            response: { use: vi.fn() },
          },
        })),
        post: vi.fn(),
      },
    }))
    vi.doMock('@/store/authStore', () => ({
      useAuthStore: {
        getState: () => ({
          tokens: { access_token: 'tok', refresh_token: 'ref' },
          logout: vi.fn(),
          setTokens: vi.fn(),
        }),
        subscribe: vi.fn(),
      },
    }))
    const axios = (await import('axios')).default
    await import('@/services/api')
    expect(axios.create).toHaveBeenCalledWith(
      expect.objectContaining({ baseURL: '/api/v1' }),
    )
  })

  it('registers request and response interceptors', async () => {
    const mockRequestUse = vi.fn()
    const mockResponseUse = vi.fn()
    vi.doMock('axios', () => ({
      default: {
        create: vi.fn(() => ({
          interceptors: {
            request: { use: mockRequestUse },
            response: { use: mockResponseUse },
          },
        })),
        post: vi.fn(),
      },
    }))
    vi.doMock('@/store/authStore', () => ({
      useAuthStore: {
        getState: () => ({
          tokens: { access_token: 'tok', refresh_token: 'ref' },
          logout: vi.fn(),
          setTokens: vi.fn(),
        }),
        subscribe: vi.fn(),
      },
    }))
    await import('@/services/api')
    expect(mockRequestUse).toHaveBeenCalled()
    expect(mockResponseUse).toHaveBeenCalled()
  })
})

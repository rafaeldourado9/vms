import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/store/authStore'

let _refreshing: Promise<string | null> | null = null

export const api: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().tokens?.access_token
  if (token && config.headers) {
    config.headers['Authorization'] = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config as InternalAxiosRequestConfig & { _retry?: boolean }

    if (err.response?.status === 401 && !original._retry) {
      original._retry = true

      const refreshToken = useAuthStore.getState().tokens?.refresh_token
      if (!refreshToken) {
        useAuthStore.getState().logout()
        window.location.href = '/login'
        return Promise.reject(err)
      }

      if (!_refreshing) {
        _refreshing = (async (): Promise<string | null> => {
          try {
            const res = await axios.post<{ access_token: string; refresh_token: string; token_type: string; expires_in: number }>(
              '/api/v1/auth/refresh',
              { refresh_token: refreshToken },
            )
            const newTokens = res.data
            const currentTokens = useAuthStore.getState().tokens!
            useAuthStore.getState().setTokens({ ...currentTokens, ...newTokens })
            return newTokens.access_token
          } catch {
            useAuthStore.getState().logout()
            window.location.href = '/login'
            return null
          } finally {
            _refreshing = null
          }
        })()
      }

      const newAccess = await _refreshing
      if (!newAccess) return Promise.reject(err)

      if (original.headers) {
        original.headers['Authorization'] = `Bearer ${newAccess}`
      }
      return api(original)
    }

    return Promise.reject(err)
  },
)

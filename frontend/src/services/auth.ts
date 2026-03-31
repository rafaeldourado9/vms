import { api } from './api'
import type { AuthTokens, User } from '@/types'

export const authService = {
  async login(email: string, password: string): Promise<AuthTokens> {
    const res = await api.post<AuthTokens>('/auth/token', { email, password })
    return res.data
  },

  async refresh(refreshToken: string): Promise<AuthTokens> {
    const res = await api.post<AuthTokens>('/auth/refresh', { refresh_token: refreshToken })
    return res.data
  },

  async me(): Promise<User> {
    const res = await api.get<User>('/users/me')
    return res.data
  },
}

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User, AuthTokens } from '@/types'

interface AuthState {
  user: User | null
  tokens: AuthTokens | null
  isAuthenticated: () => boolean
  login: (tokens: AuthTokens, user: User) => void
  logout: () => void
  setTokens: (tokens: AuthTokens) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      tokens: null,

      isAuthenticated: () => !!get().tokens?.access_token,

      login: (tokens, user) => set({ tokens, user }),

      logout: () => set({ tokens: null, user: null }),

      setTokens: (tokens) => set({ tokens }),
    }),
    { name: 'vms-auth' },
  ),
)

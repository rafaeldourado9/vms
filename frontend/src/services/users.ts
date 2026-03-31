import { api } from './api'
import type { User } from '@/types'

interface CreateUserData {
  email: string
  password: string
  full_name: string
  role?: string
}

export const usersService = {
  async list(): Promise<User[]> {
    const res = await api.get<User[]>('/users')
    return res.data
  },

  async me(): Promise<User> {
    const res = await api.get<User>('/users/me')
    return res.data
  },

  async create(data: CreateUserData): Promise<User> {
    const res = await api.post<User>('/users', data)
    return res.data
  },

  async deactivate(id: string): Promise<User> {
    const res = await api.patch<User>(`/users/${id}`, { is_active: false })
    return res.data
  },
}

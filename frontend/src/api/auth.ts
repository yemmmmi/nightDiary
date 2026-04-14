import http from './http'
import type { TokenResponse, UserResponse } from '@/types'

export interface UserUpdatePayload {
  user_name?: string
  email?: string
  gender?: string
  age?: number
  phone?: string
  address?: string
}

export const authApi = {
  login: async (user_name: string, password: string): Promise<TokenResponse> => {
    const res = await http.post('/auth/login', { user_name, password })
    return res.data
  },

  register: async (user_name: string, password: string, email?: string): Promise<UserResponse> => {
    const res = await http.post('/auth/register', { user_name, password, email })
    return res.data
  },

  me: async (): Promise<UserResponse> => {
    const res = await http.get('/auth/me')
    return res.data
  },

  updateMe: async (data: UserUpdatePayload): Promise<UserResponse> => {
    const res = await http.put('/auth/me', data)
    return res.data
  },

  logout: async (): Promise<void> => {
    await http.post('/auth/logout')
  },

  deleteMe: async (): Promise<void> => {
    await http.delete('/auth/me')
  },
}

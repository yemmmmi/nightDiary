import http from './http'
import type { TokenResponse, UserResponse } from '@/types'

export const authApi = {
  login: async (username: string, password: string): Promise<TokenResponse> => {
    const form = new URLSearchParams({ username, password })
    const res = await http.post('/auth/login', form)
    return res.data
  },

  register: async (user_name: string, email: string, password: string): Promise<TokenResponse> => {
    const res = await http.post('/auth/register', { user_name, email, password })
    return res.data
  },

  me: async (): Promise<UserResponse> => {
    const res = await http.get('/auth/me')
    return res.data
  },

  logout: async (): Promise<void> => {
    await http.post('/auth/logout')
  },
}

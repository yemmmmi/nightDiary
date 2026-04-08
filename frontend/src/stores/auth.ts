import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserResponse } from '@/types'
import { authApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<UserResponse | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  function setToken(t: string) {
    token.value = t
    localStorage.setItem('token', t)
  }

  async function login(username: string, password: string) {
    const data = await authApi.login(username, password)
    setToken(data.access_token)
  }

  async function register(username: string, email: string, password: string) {
    const data = await authApi.register(username, email, password)
    setToken(data.access_token)
  }

  async function logout() {
    try {
      await authApi.logout()
    } finally {
      token.value = null
      user.value = null
      localStorage.removeItem('token')
    }
  }

  async function fetchMe() {
    if (!token.value) return
    user.value = await authApi.me()
  }

  return { token, user, isAuthenticated, login, register, logout, fetchMe }
})

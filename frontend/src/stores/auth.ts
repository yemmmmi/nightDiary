import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserResponse } from '@/types'
import { authApi } from '@/api/auth'
import type { UserUpdatePayload } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<UserResponse | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  function setToken(t: string) {
    token.value = t
    localStorage.setItem('token', t)
  }

  function clearAuth() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  async function login(username: string, password: string) {
    const data = await authApi.login(username, password)
    setToken(data.access_token)
    await fetchMe()
  }

  async function register(username: string, password: string, email?: string) {
    // 注册成功后自动登录
    await authApi.register(username, password, email)
    await login(username, password)
  }

  async function logout() {
    try {
      await authApi.logout()
    } finally {
      clearAuth()
    }
  }

  async function fetchMe() {
    if (!token.value) return
    try {
      user.value = await authApi.me()
    } catch {
      clearAuth()
    }
  }

  async function updateProfile(data: UserUpdatePayload) {
    user.value = await authApi.updateMe(data)
  }

  async function deleteAccount() {
    await authApi.deleteMe()
    clearAuth()
  }

  // 页面刷新时自动恢复登录状态
  if (token.value) {
    fetchMe()
  }

  return {
    token, user, isAuthenticated,
    login, register, logout, fetchMe,
    updateProfile, deleteAccount,
  }
})

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserResponse } from '@/types'
import { authApi } from '@/api/auth'
import type { UserUpdatePayload } from '@/api/auth'
import { weatherApi } from '@/api/weather'

function getToken(): string | null {
  return localStorage.getItem('token') || sessionStorage.getItem('token')
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(getToken())
  const user = ref<UserResponse | null>(null)

  const isAuthenticated = computed(() => !!token.value)

  const weatherPreloaded = ref(false)
  const weatherInfo = ref<string | null>(null)

  function triggerWeatherPreheat() {
    if (weatherPreloaded.value) return
    weatherPreloaded.value = true
    weatherApi.preheat()
      .then((res) => {
        if (res.status === 'hit' || res.status === 'refreshed') {
          weatherInfo.value = res.weather
        }
      })
      .catch(() => {})
  }

  function setToken(t: string, rememberMe: boolean = false) {
    token.value = t
    if (rememberMe) {
      localStorage.setItem('token', t)
      sessionStorage.removeItem('token')
    } else {
      sessionStorage.setItem('token', t)
      localStorage.removeItem('token')
    }
    localStorage.setItem('rememberMe', String(rememberMe))
  }

  function clearAuth() {
    token.value = null
    user.value = null
    weatherPreloaded.value = false
    weatherInfo.value = null
    localStorage.removeItem('token')
    sessionStorage.removeItem('token')
    localStorage.removeItem('rememberMe')
  }

  async function login(username: string, password: string, rememberMe: boolean = false) {
    const data = await authApi.login(username, password)
    setToken(data.access_token, rememberMe)
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
      triggerWeatherPreheat()
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
    token, user, isAuthenticated, weatherInfo,
    login, register, logout, fetchMe,
    updateProfile, deleteAccount,
  }
})

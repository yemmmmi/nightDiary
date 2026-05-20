<template>
  <div class="relative flex items-center justify-center min-h-screen overflow-hidden" style="background-color: var(--bg-base);">
    <!-- 星空装饰（仅夜间可见） -->
    <div class="stars-bg absolute inset-0 pointer-events-none">
      <div class="absolute top-[10%] left-[15%] w-1 h-1 bg-star-300/50 rounded-full animate-pulse"></div>
      <div class="absolute top-[20%] right-[25%] w-1.5 h-1.5 bg-star-200/30 rounded-full animate-pulse" style="animation-delay: 1s"></div>
      <div class="absolute top-[35%] left-[40%] w-1 h-1 bg-star-300/40 rounded-full animate-pulse" style="animation-delay: 2s"></div>
      <div class="absolute top-[60%] right-[15%] w-1 h-1 bg-white/20 rounded-full animate-pulse" style="animation-delay: 1.5s"></div>
      <div class="absolute bottom-[25%] left-[30%] w-1 h-1 bg-star-200/25 rounded-full animate-pulse" style="animation-delay: 2.5s"></div>
    </div>

    <!-- 背景光晕 -->
    <div class="absolute top-10 right-20 w-64 h-64 rounded-full blur-[80px]" style="background: color-mix(in srgb, var(--accent), transparent 92%)"></div>
    <div class="absolute bottom-20 left-10 w-80 h-80 rounded-full blur-[100px]" style="background: color-mix(in srgb, var(--accent), transparent 95%)"></div>

    <div class="relative w-full max-w-md mx-4">
      <div class="glass-card rounded-3xl p-10">
        <!-- Logo -->
        <div class="text-center mb-10">
          <div class="inline-flex items-center justify-center w-20 h-20 rounded-2xl mb-5 animate-float"
               style="background: var(--accent-soft);">
            <span class="text-4xl">🌙</span>
          </div>
          <h1 class="text-3xl font-bold font-serif" style="color: var(--text-primary);">夜记</h1>
          <p class="mt-2 text-sm" style="color: var(--text-muted);">记录生活，温暖每一个夜晚</p>
        </div>

        <form @submit.prevent="handleLogin" class="space-y-5">
          <div>
            <label for="username" class="block text-sm font-medium mb-1.5" style="color: var(--text-secondary);">用户名</label>
            <input id="username" v-model="form.username" type="text" required autocomplete="username"
              placeholder="请输入用户名" class="input-theme" />
          </div>
          <div>
            <label for="password" class="block text-sm font-medium mb-1.5" style="color: var(--text-secondary);">密码</label>
            <input id="password" v-model="form.password" type="password" required autocomplete="current-password"
              placeholder="请输入密码" class="input-theme" />
          </div>

          <div class="flex items-center">
            <input id="rememberMe" v-model="rememberMe" type="checkbox"
              class="w-4 h-4 rounded" style="accent-color: var(--accent);" />
            <label for="rememberMe" class="ml-2 text-sm" style="color: var(--text-muted);">记住我</label>
          </div>

          <p v-if="errorMsg" class="text-red-500 text-sm px-3 py-2 rounded-lg" style="background: rgba(239,68,68,0.08);" role="alert">{{ errorMsg }}</p>

          <button type="submit" :disabled="loading" class="w-full py-3.5 btn-primary text-lg">
            {{ loading ? '登录中...' : '登录' }}
          </button>
        </form>

        <p class="mt-8 text-center text-sm" style="color: var(--text-muted);">
          还没有账号？
          <router-link to="/register" class="font-medium transition" style="color: var(--accent);">立即注册</router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTheme } from '@/composables/useTheme'

useTheme()

const router = useRouter()
const auth = useAuthStore()
const form = reactive({ username: '', password: '' })
const rememberMe = ref(false)
const loading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  errorMsg.value = ''
  loading.value = true
  try {
    await auth.login(form.username, form.password, rememberMe.value)
    router.push('/diary')
  } catch (err: any) {
    errorMsg.value = err.response?.data?.detail || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>

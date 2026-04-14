<template>
  <div class="flex items-center justify-center min-h-screen bg-gradient-to-br from-diary-50 via-amber-50 to-diary-100">
    <!-- 装饰性背景 -->
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div class="absolute top-20 left-10 w-64 h-64 bg-diary-200/30 rounded-full blur-3xl"></div>
      <div class="absolute bottom-20 right-10 w-80 h-80 bg-diary-300/20 rounded-full blur-3xl"></div>
    </div>

    <div class="relative w-full max-w-md mx-4">
      <!-- 卡片 -->
      <div class="bg-white/80 backdrop-blur-sm rounded-3xl shadow-xl shadow-diary-200/50 p-10 border border-diary-100">
        <!-- Logo -->
        <div class="text-center mb-8">
          <div class="inline-flex items-center justify-center w-16 h-16 bg-diary-100 rounded-2xl mb-4">
            <span class="text-3xl">🌙</span>
          </div>
          <h1 class="text-3xl font-bold text-ink-800 font-serif">夜记</h1>
          <p class="text-ink-400 mt-2 text-sm">记录生活，温暖每一个夜晚</p>
        </div>

        <form @submit.prevent="handleLogin" class="space-y-5">
          <div>
            <label for="username" class="block text-sm font-medium text-ink-600 mb-1.5">用户名</label>
            <input
              id="username" v-model="form.username" type="text" required autocomplete="username"
              placeholder="请输入用户名"
              class="w-full px-4 py-3 bg-diary-50/50 border border-diary-200 rounded-xl focus:ring-2 focus:ring-diary-400 focus:border-transparent outline-none transition placeholder:text-ink-300"
            />
          </div>

          <div>
            <label for="password" class="block text-sm font-medium text-ink-600 mb-1.5">密码</label>
            <input
              id="password" v-model="form.password" type="password" required autocomplete="current-password"
              placeholder="请输入密码"
              class="w-full px-4 py-3 bg-diary-50/50 border border-diary-200 rounded-xl focus:ring-2 focus:ring-diary-400 focus:border-transparent outline-none transition placeholder:text-ink-300"
            />
          </div>

          <p v-if="errorMsg" class="text-red-500 text-sm bg-red-50 px-3 py-2 rounded-lg" role="alert">{{ errorMsg }}</p>

          <button
            type="submit" :disabled="loading"
            class="w-full py-3 bg-gradient-to-r from-diary-500 to-diary-600 text-white rounded-xl font-semibold hover:from-diary-600 hover:to-diary-700 disabled:opacity-50 disabled:cursor-not-allowed transition shadow-lg shadow-diary-300/40"
          >
            {{ loading ? '登录中...' : '登录' }}
          </button>
        </form>

        <p class="mt-8 text-center text-sm text-ink-400">
          还没有账号？
          <router-link to="/register" class="text-diary-600 hover:text-diary-700 font-medium">立即注册</router-link>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const form = reactive({ username: '', password: '' })
const loading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  errorMsg.value = ''
  loading.value = true
  try {
    await auth.login(form.username, form.password)
    router.push('/diary')
  } catch (err: any) {
    errorMsg.value = err.response?.data?.detail || '登录失败，请检查用户名和密码'
  } finally {
    loading.value = false
  }
}
</script>

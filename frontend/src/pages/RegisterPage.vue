<template>
  <div class="flex items-center justify-center min-h-screen bg-gradient-to-br from-diary-50 via-amber-50 to-diary-100">
    <div class="absolute inset-0 overflow-hidden pointer-events-none">
      <div class="absolute top-32 right-20 w-72 h-72 bg-diary-200/30 rounded-full blur-3xl"></div>
      <div class="absolute bottom-10 left-16 w-60 h-60 bg-diary-300/20 rounded-full blur-3xl"></div>
    </div>

    <div class="relative w-full max-w-md mx-4">
      <div class="bg-white/80 backdrop-blur-sm rounded-3xl shadow-xl shadow-diary-200/50 p-10 border border-diary-100">
        <div class="text-center mb-8">
          <div class="inline-flex items-center justify-center w-16 h-16 bg-diary-100 rounded-2xl mb-4">
            <span class="text-3xl">✨</span>
          </div>
          <h1 class="text-3xl font-bold text-ink-800 font-serif">创建账号</h1>
          <p class="text-ink-400 mt-2 text-sm">加入夜记，开始记录你的故事</p>
        </div>

        <form @submit.prevent="handleRegister" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-ink-600 mb-1.5">用户名</label>
            <input v-model="form.username" type="text" required autocomplete="username" placeholder="请输入用户名"
              class="w-full px-4 py-3 bg-diary-50/50 border border-diary-200 rounded-xl focus:ring-2 focus:ring-diary-400 focus:border-transparent outline-none transition placeholder:text-ink-300" />
          </div>
          <div>
            <label class="block text-sm font-medium text-ink-600 mb-1.5">邮箱（选填）</label>
            <input v-model="form.email" type="email" autocomplete="email" placeholder="请输入邮箱"
              class="w-full px-4 py-3 bg-diary-50/50 border border-diary-200 rounded-xl focus:ring-2 focus:ring-diary-400 focus:border-transparent outline-none transition placeholder:text-ink-300" />
          </div>
          <div>
            <label class="block text-sm font-medium text-ink-600 mb-1.5">密码</label>
            <input v-model="form.password" type="password" required autocomplete="new-password" placeholder="至少 6 位"
              class="w-full px-4 py-3 bg-diary-50/50 border border-diary-200 rounded-xl focus:ring-2 focus:ring-diary-400 focus:border-transparent outline-none transition placeholder:text-ink-300" />
          </div>
          <div>
            <label class="block text-sm font-medium text-ink-600 mb-1.5">确认密码</label>
            <input v-model="form.confirmPassword" type="password" required autocomplete="new-password" placeholder="再次输入密码"
              class="w-full px-4 py-3 bg-diary-50/50 border border-diary-200 rounded-xl focus:ring-2 focus:ring-diary-400 focus:border-transparent outline-none transition placeholder:text-ink-300" />
          </div>

          <p v-if="errorMsg" class="text-red-500 text-sm bg-red-50 px-3 py-2 rounded-lg">{{ errorMsg }}</p>

          <button type="submit" :disabled="loading"
            class="w-full py-3 bg-gradient-to-r from-diary-500 to-diary-600 text-white rounded-xl font-semibold hover:from-diary-600 hover:to-diary-700 disabled:opacity-50 transition shadow-lg shadow-diary-300/40">
            {{ loading ? '注册中...' : '注册' }}
          </button>
        </form>

        <p class="mt-8 text-center text-sm text-ink-400">
          已有账号？<router-link to="/login" class="text-diary-600 hover:text-diary-700 font-medium">去登录</router-link>
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
const form = reactive({ username: '', email: '', password: '', confirmPassword: '' })
const loading = ref(false)
const errorMsg = ref('')

async function handleRegister() {
  errorMsg.value = ''
  if (form.password !== form.confirmPassword) { errorMsg.value = '两次输入的密码不一致'; return }
  if (form.password.length < 6) { errorMsg.value = '密码长度不能少于 6 位'; return }
  loading.value = true
  try {
    await auth.register(form.username, form.password, form.email || undefined)
    router.push('/diary')
  } catch (err: any) {
    errorMsg.value = err.response?.data?.detail || '注册失败'
  } finally { loading.value = false }
}
</script>

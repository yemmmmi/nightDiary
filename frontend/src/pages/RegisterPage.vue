<template>
  <div class="relative flex items-center justify-center min-h-screen overflow-hidden" style="background-color: var(--bg-base);">
    <div class="stars-bg absolute inset-0 pointer-events-none">
      <div class="absolute top-[15%] left-[25%] w-1 h-1 bg-star-300/40 rounded-full animate-pulse" style="animation-delay: 0.5s"></div>
      <div class="absolute top-[25%] right-[20%] w-1.5 h-1.5 bg-star-200/30 rounded-full animate-pulse" style="animation-delay: 1.5s"></div>
      <div class="absolute top-[50%] left-[10%] w-1 h-1 bg-star-300/25 rounded-full animate-pulse" style="animation-delay: 2s"></div>
    </div>

    <div class="absolute top-20 left-20 w-40 h-40 rounded-full blur-[80px]" style="background: color-mix(in srgb, var(--accent), transparent 93%)"></div>

    <div class="relative w-full max-w-md mx-4">
      <div class="glass-card rounded-3xl p-10">
        <div class="text-center mb-8">
          <div class="inline-flex items-center justify-center w-16 h-16 rounded-2xl mb-4 animate-float" style="background: var(--accent-soft);">
            <span class="text-3xl">✨</span>
          </div>
          <h1 class="text-3xl font-bold font-serif" style="color: var(--text-primary);">创建账号</h1>
          <p class="mt-2 text-sm" style="color: var(--text-muted);">加入夜记，开始记录你的故事</p>
        </div>

        <form @submit.prevent="handleRegister" class="space-y-4">
          <div>
            <label class="block text-sm font-medium mb-1.5" style="color: var(--text-secondary);">用户名</label>
            <input v-model="form.username" type="text" required autocomplete="username" placeholder="请输入用户名" class="input-theme" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-1.5" style="color: var(--text-secondary);">邮箱（选填）</label>
            <input v-model="form.email" type="email" autocomplete="email" placeholder="请输入邮箱" class="input-theme" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-1.5" style="color: var(--text-secondary);">密码</label>
            <input v-model="form.password" type="password" required autocomplete="new-password" placeholder="至少 6 位" class="input-theme" />
          </div>
          <div>
            <label class="block text-sm font-medium mb-1.5" style="color: var(--text-secondary);">确认密码</label>
            <input v-model="form.confirmPassword" type="password" required autocomplete="new-password" placeholder="再次输入密码" class="input-theme" />
          </div>

          <p v-if="errorMsg" class="text-red-500 text-sm px-3 py-2 rounded-lg" style="background: rgba(239,68,68,0.08);">{{ errorMsg }}</p>

          <button type="submit" :disabled="loading" class="w-full py-3.5 btn-primary text-lg">
            {{ loading ? '注册中...' : '注册' }}
          </button>
        </form>

        <p class="mt-8 text-center text-sm" style="color: var(--text-muted);">
          已有账号？<router-link to="/login" class="font-medium transition" style="color: var(--accent);">去登录</router-link>
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

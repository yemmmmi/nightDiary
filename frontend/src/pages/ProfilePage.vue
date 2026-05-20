<template>
  <div class="min-h-screen py-12 px-6" style="background-color: var(--bg-base);">
    <div class="max-w-2xl mx-auto">
      <div class="flex items-center justify-between mb-8">
        <h1 class="text-2xl font-bold font-serif" style="color: var(--text-primary);">个人中心</h1>
        <router-link to="/diary" class="text-sm transition" style="color: var(--accent);">← 返回日记</router-link>
      </div>

      <div v-if="!user" style="color: var(--text-faint);">加载中...</div>

      <form v-else @submit.prevent="handleSave" class="glass-card rounded-2xl p-6 space-y-5">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="block text-xs mb-1" style="color: var(--text-faint);">用户名</label>
            <input v-model="form.user_name" type="text" class="input-theme" />
          </div>
          <div>
            <label class="block text-xs mb-1" style="color: var(--text-faint);">邮箱</label>
            <input v-model="form.email" type="email" class="input-theme" />
          </div>
          <div>
            <label class="block text-xs mb-1" style="color: var(--text-faint);">性别</label>
            <select v-model="form.gender" class="input-theme">
              <option value="">未设置</option>
              <option value="M">男</option>
              <option value="F">女</option>
              <option value="Other">其他</option>
            </select>
          </div>
          <div>
            <label class="block text-xs mb-1" style="color: var(--text-faint);">年龄</label>
            <input v-model.number="form.age" type="number" min="1" max="150" class="input-theme" />
          </div>
          <div>
            <label class="block text-xs mb-1" style="color: var(--text-faint);">电话</label>
            <input v-model="form.phone" type="tel" class="input-theme" />
          </div>
          <div>
            <label class="block text-xs mb-1" style="color: var(--text-faint);">地址</label>
            <input v-model="form.address" type="text" placeholder="用于天气查询" class="input-theme" />
          </div>
        </div>

        <p v-if="msg" :class="msgIsError ? 'text-red-500' : 'text-green-500'" class="text-sm">{{ msg }}</p>

        <div class="flex justify-between items-center pt-2">
          <button type="submit" :disabled="saving" class="px-6 py-2.5 btn-primary text-sm">
            {{ saving ? '保存中...' : '保存修改' }}
          </button>
          <button type="button" @click="showDeleteConfirm = true"
            class="px-4 py-2 text-red-400/70 hover:text-red-500 rounded-lg transition text-sm">
            注销账号
          </button>
        </div>
      </form>

      <!-- 注销确认 -->
      <div v-if="showDeleteConfirm" class="fixed inset-0 flex items-center justify-center z-50" style="background: rgba(0,0,0,0.5); backdrop-filter: blur(4px);">
        <div class="glass-card p-6 rounded-2xl max-w-sm w-full mx-4">
          <h3 class="text-lg font-semibold mb-2" style="color: var(--text-primary);">确认注销账号？</h3>
          <p class="text-sm mb-6" style="color: var(--text-muted);">此操作不可撤销，你的所有数据将被永久删除。</p>
          <div class="flex justify-end gap-3">
            <button @click="showDeleteConfirm = false" class="px-4 py-2 rounded-lg transition" style="color: var(--text-secondary);">取消</button>
            <button @click="handleDelete" :disabled="deleting"
              class="px-4 py-2 bg-red-500/15 text-red-500 border border-red-500/30 rounded-lg hover:bg-red-500/25 disabled:opacity-50 transition">
              {{ deleting ? '处理中...' : '确认注销' }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watchEffect } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { storeToRefs } from 'pinia'

const router = useRouter()
const auth = useAuthStore()
const { user } = storeToRefs(auth)

const form = reactive({ user_name: '', email: '', gender: '', age: null as number | null, phone: '', address: '' })
const saving = ref(false)
const deleting = ref(false)
const msg = ref('')
const msgIsError = ref(false)
const showDeleteConfirm = ref(false)

watchEffect(() => {
  if (user.value) {
    form.user_name = user.value.user_name || ''
    form.email = user.value.email || ''
    form.gender = user.value.gender || ''
    form.age = user.value.age
    form.phone = user.value.phone || ''
    form.address = user.value.address || ''
  }
})

async function handleSave() {
  msg.value = ''; saving.value = true
  try {
    const payload: Record<string, any> = {}
    if (form.user_name) payload.user_name = form.user_name
    if (form.email) payload.email = form.email
    if (form.gender) payload.gender = form.gender
    if (form.age) payload.age = form.age
    if (form.phone) payload.phone = form.phone
    if (form.address) payload.address = form.address
    await auth.updateProfile(payload)
    msg.value = '保存成功'; msgIsError.value = false
  } catch (err: any) { msg.value = err.response?.data?.detail || '保存失败'; msgIsError.value = true }
  finally { saving.value = false }
}

async function handleDelete() {
  deleting.value = true
  try { await auth.deleteAccount(); router.push('/login') }
  catch (err: any) { msg.value = err.response?.data?.detail || '注销失败'; msgIsError.value = true; showDeleteConfirm.value = false }
  finally { deleting.value = false }
}
</script>

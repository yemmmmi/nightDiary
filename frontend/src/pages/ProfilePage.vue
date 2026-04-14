<template>
  <div class="max-w-2xl mx-auto p-6">
    <h1 class="text-2xl font-bold text-gray-800 mb-6">个人中心</h1>

    <div v-if="!user" class="text-gray-500">加载中...</div>

    <form v-else @submit.prevent="handleSave" class="space-y-5 bg-white p-6 rounded-xl shadow">
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">用户名</label>
          <input
            v-model="form.user_name"
            type="text"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">邮箱</label>
          <input
            v-model="form.email"
            type="email"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">性别</label>
          <select
            v-model="form.gender"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          >
            <option value="">未设置</option>
            <option value="M">男</option>
            <option value="F">女</option>
            <option value="Other">其他</option>
          </select>
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">年龄</label>
          <input
            v-model.number="form.age"
            type="number"
            min="1"
            max="150"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">电话</label>
          <input
            v-model="form.phone"
            type="tel"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">地址</label>
          <input
            v-model="form.address"
            type="text"
            placeholder="用于天气查询"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          />
        </div>
      </div>

      <p v-if="msg" :class="msgIsError ? 'text-red-500' : 'text-green-600'" class="text-sm">{{ msg }}</p>

      <div class="flex justify-between items-center pt-2">
        <button
          type="submit"
          :disabled="saving"
          class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
        >
          {{ saving ? '保存中...' : '保存修改' }}
        </button>

        <button
          type="button"
          @click="showDeleteConfirm = true"
          class="px-4 py-2 text-red-600 hover:bg-red-50 rounded-lg transition text-sm"
        >
          注销账号
        </button>
      </div>
    </form>

    <!-- 注销确认弹窗 -->
    <div v-if="showDeleteConfirm" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white p-6 rounded-xl shadow-xl max-w-sm w-full mx-4">
        <h3 class="text-lg font-semibold text-gray-800 mb-2">确认注销账号？</h3>
        <p class="text-gray-500 text-sm mb-6">此操作不可撤销，你的所有数据将被永久删除。</p>
        <div class="flex justify-end gap-3">
          <button
            @click="showDeleteConfirm = false"
            class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition"
          >
            取消
          </button>
          <button
            @click="handleDelete"
            :disabled="deleting"
            class="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition"
          >
            {{ deleting ? '处理中...' : '确认注销' }}
          </button>
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

const form = reactive({
  user_name: '',
  email: '',
  gender: '',
  age: null as number | null,
  phone: '',
  address: '',
})

const saving = ref(false)
const deleting = ref(false)
const msg = ref('')
const msgIsError = ref(false)
const showDeleteConfirm = ref(false)

// 用户数据加载后填充表单
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
  msg.value = ''
  saving.value = true
  try {
    const payload: Record<string, any> = {}
    if (form.user_name) payload.user_name = form.user_name
    if (form.email) payload.email = form.email
    if (form.gender) payload.gender = form.gender
    if (form.age) payload.age = form.age
    if (form.phone) payload.phone = form.phone
    if (form.address) payload.address = form.address

    await auth.updateProfile(payload)
    msg.value = '保存成功'
    msgIsError.value = false
  } catch (err: any) {
    msg.value = err.response?.data?.detail || '保存失败'
    msgIsError.value = true
  } finally {
    saving.value = false
  }
}

async function handleDelete() {
  deleting.value = true
  try {
    await auth.deleteAccount()
    router.push('/login')
  } catch (err: any) {
    msg.value = err.response?.data?.detail || '注销失败'
    msgIsError.value = true
    showDeleteConfirm.value = false
  } finally {
    deleting.value = false
  }
}
</script>

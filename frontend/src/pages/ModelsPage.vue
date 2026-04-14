<template>
  <div class="max-w-3xl mx-auto p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">模型管理</h1>
      <router-link to="/diary" class="text-sm text-blue-600 hover:underline">← 返回日记</router-link>
    </div>

    <!-- 注册新模型 -->
    <div class="bg-white rounded-xl shadow p-5 mb-6">
      <h2 class="text-sm font-semibold text-gray-700 mb-3">注册新模型</h2>
      <form @submit.prevent="handleCreate" class="space-y-3">
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-xs text-gray-500 mb-1">模型名称</label>
            <input
              v-model="form.model_name"
              type="text"
              placeholder="如 deepseek-chat"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            />
          </div>
          <div>
            <label class="block text-xs text-gray-500 mb-1">Base URL</label>
            <input
              v-model="form.base_url"
              type="url"
              required
              placeholder="https://api.deepseek.com"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
            />
          </div>
        </div>
        <div>
          <label class="block text-xs text-gray-500 mb-1">API Key</label>
          <input
            v-model="form.model_key"
            type="password"
            required
            placeholder="sk-..."
            autocomplete="off"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          />
        </div>
        <button
          type="submit"
          :disabled="!form.model_key || !form.base_url || creating"
          class="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40 transition text-sm"
        >
          {{ creating ? '注册中...' : '注册模型' }}
        </button>
      </form>
      <p v-if="error" class="mt-2 text-red-500 text-sm">{{ error }}</p>
    </div>

    <!-- 模型列表 -->
    <div v-if="loading" class="text-center py-8 text-gray-400">加载中...</div>
    <div v-else-if="!models.length" class="text-center py-8 text-gray-400">暂无模型配置</div>
    <div v-else class="space-y-3">
      <div
        v-for="model in models"
        :key="model.id"
        class="bg-white rounded-lg shadow-sm p-4 flex items-center justify-between"
      >
        <div>
          <div class="flex items-center gap-2">
            <span class="font-medium text-gray-800">{{ model.model_name }}</span>
            <span
              :class="model.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'"
              class="px-2 py-0.5 rounded-full text-xs"
            >
              {{ model.is_active ? '活跃' : '未激活' }}
            </span>
          </div>
          <p class="text-xs text-gray-400 mt-1">{{ model.base_url }}</p>
        </div>
        <button
          @click="handleDelete(model.id)"
          class="text-sm text-red-500 hover:text-red-600 transition"
        >
          删除
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { modelsApi } from '@/api/models'
import type { ModelResponse } from '@/types'

const models = ref<ModelResponse[]>([])
const loading = ref(true)
const creating = ref(false)
const error = ref('')
const form = reactive({ model_name: '', model_key: '', base_url: '' })

onMounted(fetchModels)

async function fetchModels() {
  loading.value = true
  try { models.value = await modelsApi.list() } catch {}
  loading.value = false
}

async function handleCreate() {
  if (!form.model_key || !form.base_url) return
  creating.value = true
  error.value = ''
  try {
    await modelsApi.create({
      model_name: form.model_name || '未命名',
      model_key: form.model_key,
      base_url: form.base_url,
    })
    form.model_name = ''
    form.model_key = ''
    form.base_url = ''
    await fetchModels()
  } catch (err: any) {
    error.value = err.response?.data?.detail || '注册失败'
  }
  creating.value = false
}

async function handleDelete(id: number) {
  try {
    await modelsApi.delete(id)
    models.value = models.value.filter(m => m.id !== id)
  } catch (err: any) {
    error.value = err.response?.data?.detail || '删除失败'
  }
}
</script>

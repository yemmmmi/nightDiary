<template>
  <div class="min-h-screen py-12 px-6" style="background-color: var(--bg-base);">
    <div class="max-w-3xl mx-auto">
      <div class="flex items-center justify-between mb-8">
        <h1 class="text-2xl font-bold font-serif" style="color: var(--text-primary);">模型管理</h1>
        <router-link to="/diary" class="text-sm transition" style="color: var(--accent);">← 返回日记</router-link>
      </div>

      <!-- 注册新模型 -->
      <div class="glass-card rounded-2xl p-6 mb-6">
        <h2 class="text-sm font-semibold mb-4" style="color: var(--text-secondary);">注册新模型</h2>
        <form @submit.prevent="handleCreate" class="space-y-4">
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="block text-xs mb-1" style="color: var(--text-faint);">模型名称</label>
              <input v-model="form.model_name" type="text" placeholder="如 deepseek-chat" class="input-theme" />
            </div>
            <div>
              <label class="block text-xs mb-1" style="color: var(--text-faint);">Base URL</label>
              <input v-model="form.base_url" type="url" required placeholder="https://api.deepseek.com" class="input-theme" />
            </div>
          </div>
          <div>
            <label class="block text-xs mb-1" style="color: var(--text-faint);">API Key</label>
            <input v-model="form.model_key" type="password" required placeholder="sk-..." autocomplete="off" class="input-theme" />
          </div>
          <button type="submit" :disabled="!form.model_key || !form.base_url || creating" class="px-6 py-2.5 btn-primary text-sm">
            {{ creating ? '注册中...' : '注册模型' }}
          </button>
        </form>
        <p v-if="error" class="mt-3 text-red-500 text-sm">{{ error }}</p>
      </div>

      <!-- 模型列表 -->
      <div v-if="loading" class="text-center py-12" style="color: var(--text-faint);">加载中...</div>
      <div v-else-if="!models.length" class="text-center py-12" style="color: var(--text-faint);">暂无模型配置</div>
      <div v-else class="space-y-3">
        <div v-for="model in models" :key="model.id" class="glass-card rounded-xl p-5 flex items-center justify-between">
          <div>
            <div class="flex items-center gap-2.5">
              <span class="font-medium" style="color: var(--text-primary);">{{ model.model_name }}</span>
              <span class="px-2.5 py-0.5 rounded-full text-xs border"
                :class="model.is_active ? 'text-green-500 border-green-500/30 bg-green-500/10' : 'border-transparent'"
                :style="!model.is_active ? { color: 'var(--text-faint)', background: 'var(--bg-input)', borderColor: 'var(--border-base)' } : {}">
                {{ model.is_active ? '活跃' : '未激活' }}
              </span>
            </div>
            <p class="text-xs mt-1" style="color: var(--text-faint);">{{ model.base_url }}</p>
          </div>
          <div class="flex items-center gap-3">
            <button v-if="!model.is_active" @click="handleActivate(model.id)"
              class="text-sm text-green-500 hover:text-green-400 font-medium transition px-3 py-1 rounded-lg hover:bg-green-500/10">
              激活
            </button>
            <button @click="handleDelete(model.id)"
              class="text-sm text-red-400/70 hover:text-red-500 transition px-3 py-1 rounded-lg hover:bg-red-500/10">
              删除
            </button>
          </div>
        </div>
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
  creating.value = true; error.value = ''
  try {
    await modelsApi.create({ model_name: form.model_name || '未命名', model_key: form.model_key, base_url: form.base_url })
    form.model_name = ''; form.model_key = ''; form.base_url = ''
    await fetchModels()
  } catch (err: any) { error.value = err.response?.data?.detail || '注册失败' }
  creating.value = false
}

async function handleDelete(id: number) {
  try { await modelsApi.delete(id); models.value = models.value.filter(m => m.id !== id) }
  catch (err: any) { error.value = err.response?.data?.detail || '删除失败' }
}

async function handleActivate(id: number) {
  error.value = ''
  try { await modelsApi.activate(id); await fetchModels() }
  catch (err: any) { error.value = err.response?.data?.detail || '激活失败' }
}
</script>

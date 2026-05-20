<template>
  <div class="min-h-screen py-12 px-6" style="background-color: var(--bg-base);">
    <div class="max-w-3xl mx-auto">
      <div class="flex items-center justify-between mb-8">
        <h1 class="text-2xl font-bold font-serif" style="color: var(--text-primary);">标签管理</h1>
        <router-link to="/diary" class="text-sm transition" style="color: var(--accent);">← 返回日记</router-link>
      </div>

      <div class="glass-card rounded-2xl p-6 mb-6">
        <form @submit.prevent="handleCreate" class="flex gap-3 items-end">
          <div class="flex-1">
            <label class="block text-xs mb-1" style="color: var(--text-faint);">标签名称</label>
            <input v-model="newTag.name" type="text" maxlength="15" placeholder="最多 15 字" class="input-theme" />
          </div>
          <div>
            <label class="block text-xs mb-1" style="color: var(--text-faint);">颜色</label>
            <input v-model="newTag.color" type="color" class="w-10 h-10 rounded-lg cursor-pointer border" style="border-color: var(--border-base); background: var(--bg-input);" />
          </div>
          <button type="submit" :disabled="!newTag.name.trim() || creating" class="px-5 py-3 btn-primary text-sm">
            {{ creating ? '...' : '添加' }}
          </button>
        </form>
        <p v-if="error" class="mt-3 text-red-500 text-sm">{{ error }}</p>
        <p v-if="successMsg" class="mt-3 text-green-500 text-sm">{{ successMsg }}</p>
      </div>

      <div v-if="loading" class="text-center py-12" style="color: var(--text-faint);">加载中...</div>
      <div v-else-if="!tags.length" class="text-center py-12" style="color: var(--text-faint);">暂无标签</div>
      <div v-else class="space-y-2">
        <div v-for="tag in tags" :key="tag.id" class="glass-card rounded-xl p-4 flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="w-3.5 h-3.5 rounded-full" :style="{ backgroundColor: tag.color || '#6B7280' }"></span>
            <span class="font-medium" style="color: var(--text-primary);">#{{ tag.tag_name }}</span>
            <span v-if="tag.status === 'pending'" class="text-xs px-2 py-0.5 rounded-full text-amber-500 bg-amber-500/10">待审核</span>
            <span class="text-xs" style="color: var(--text-faint);">引用 {{ tag.usage_count }} 次</span>
            <span class="text-xs" style="color: var(--text-faint);">by {{ tag.creator }}</span>
          </div>
          <button @click="handleDelete(tag.id)" class="text-sm text-red-400/70 hover:text-red-500 transition px-2 py-1 rounded-lg">删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { tagsApi } from '@/api/tags'
import type { TagResponse } from '@/types'

const tags = ref<TagResponse[]>([])
const loading = ref(true)
const creating = ref(false)
const error = ref('')
const successMsg = ref('')
const newTag = reactive({ name: '', color: '#a78bfa' })

onMounted(fetchTags)

async function fetchTags() {
  loading.value = true
  try { tags.value = await tagsApi.list() } catch {}
  loading.value = false
}

async function handleCreate() {
  if (!newTag.name.trim()) return
  creating.value = true; error.value = ''; successMsg.value = ''
  try {
    const created = await tagsApi.create(newTag.name, newTag.color)
    newTag.name = ''
    if (created.status === 'pending') {
      successMsg.value = '标签已提交，等待管理员审核'
    }
    await fetchTags()
  }
  catch (err: any) { error.value = err.response?.data?.detail || '创建失败' }
  creating.value = false
}

async function handleDelete(id: number) {
  try { await tagsApi.delete(id); tags.value = tags.value.filter(t => t.id !== id) }
  catch (err: any) { error.value = err.response?.data?.detail || '删除失败' }
}
</script>

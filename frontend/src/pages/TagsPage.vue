<template>
  <div class="max-w-3xl mx-auto p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">标签管理</h1>
      <router-link to="/diary" class="text-sm text-blue-600 hover:underline">← 返回日记</router-link>
    </div>

    <!-- 新增标签 -->
    <div class="bg-white rounded-xl shadow p-5 mb-6">
      <form @submit.prevent="handleCreate" class="flex gap-3 items-end">
        <div class="flex-1">
          <label class="block text-sm font-medium text-gray-700 mb-1">标签名称</label>
          <input
            v-model="newTag.name"
            type="text"
            maxlength="15"
            placeholder="最多 15 字"
            class="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">颜色</label>
          <input v-model="newTag.color" type="color" class="w-10 h-10 rounded cursor-pointer" />
        </div>
        <button
          type="submit"
          :disabled="!newTag.name.trim() || creating"
          class="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40 transition"
        >
          {{ creating ? '...' : '添加' }}
        </button>
      </form>
      <p v-if="error" class="mt-2 text-red-500 text-sm">{{ error }}</p>
    </div>

    <!-- 标签列表 -->
    <div v-if="loading" class="text-center py-8 text-gray-400">加载中...</div>
    <div v-else-if="!tags.length" class="text-center py-8 text-gray-400">暂无标签</div>
    <div v-else class="space-y-2">
      <div
        v-for="tag in tags"
        :key="tag.id"
        class="bg-white rounded-lg shadow-sm p-4 flex items-center justify-between"
      >
        <div class="flex items-center gap-3">
          <span class="w-4 h-4 rounded-full" :style="{ backgroundColor: tag.color || '#6B7280' }"></span>
          <span class="font-medium text-gray-800">#{{ tag.tag_name }}</span>
          <span class="text-xs text-gray-400">引用 {{ tag.usage_count }} 次</span>
          <span class="text-xs text-gray-400">by {{ tag.creator }}</span>
        </div>
        <button
          @click="handleDelete(tag.id)"
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
import { tagsApi } from '@/api/tags'
import type { TagResponse } from '@/types'

const tags = ref<TagResponse[]>([])
const loading = ref(true)
const creating = ref(false)
const error = ref('')
const newTag = reactive({ name: '', color: '#3b82f6' })

onMounted(fetchTags)

async function fetchTags() {
  loading.value = true
  try { tags.value = await tagsApi.list() } catch {}
  loading.value = false
}

async function handleCreate() {
  if (!newTag.name.trim()) return
  creating.value = true
  error.value = ''
  try {
    await tagsApi.create(newTag.name, newTag.color)
    newTag.name = ''
    await fetchTags()
  } catch (err: any) {
    error.value = err.response?.data?.detail || '创建失败'
  }
  creating.value = false
}

async function handleDelete(id: number) {
  try {
    await tagsApi.delete(id)
    tags.value = tags.value.filter(t => t.id !== id)
  } catch (err: any) {
    error.value = err.response?.data?.detail || '删除失败'
  }
}
</script>

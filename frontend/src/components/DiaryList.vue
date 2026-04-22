<template>
  <div>
    <div v-if="loading" class="text-center py-20 text-ink-300 text-xl">
      <span class="text-4xl block mb-4">📖</span>加载中...
    </div>

    <div v-else-if="!entries.length" class="text-center py-24">
      <span class="text-7xl block mb-6">🌙</span>
      <p class="text-ink-400 font-serif text-2xl">还没有日记</p>
      <p class="text-ink-300 text-lg mt-3">写下今天的第一篇吧</p>
    </div>

    <div v-else class="space-y-6">
      <div
        v-for="entry in entries" :key="entry.NID"
        @click="$emit('select', entry)"
        class="group bg-white/70 backdrop-blur-sm rounded-3xl border border-diary-100 p-8 hover:shadow-lg hover:shadow-diary-200/40 hover:border-diary-200 transition-all cursor-pointer"
      >
        <div class="flex items-center justify-between mb-5">
          <div class="flex items-center gap-3">
            <span class="text-base text-ink-400 bg-diary-50 px-4 py-2 rounded-full">{{ formatDate(entry.create_time) }}</span>
            <span v-if="entry.is_open" class="text-sm text-diary-500 bg-diary-50 px-3 py-1 rounded-full">公开</span>
            <span v-else class="text-sm text-ink-300 bg-ink-50 px-3 py-1 rounded-full">私密</span>
          </div>
          <div class="flex items-center gap-4">
            <span v-if="entry.weather" class="text-base text-ink-300">{{ entry.weather }}</span>
            <button
              v-if="entry.is_open && !entry.published_to_column"
              @click.stop="handlePublish(entry.NID)"
              class="opacity-0 group-hover:opacity-100 text-base text-diary-500 hover:text-diary-600 transition px-3 py-1 rounded-lg hover:bg-diary-50"
            >
              发布专栏
            </button>
            <button
              v-if="entry.published_to_column"
              @click.stop="handleUnpublish(entry.NID)"
              class="opacity-0 group-hover:opacity-100 text-base text-amber-500 hover:text-amber-600 transition px-3 py-1 rounded-lg hover:bg-amber-50"
            >
              下架专栏
            </button>
            <button
              @click.stop="handleDelete(entry.NID)"
              class="opacity-0 group-hover:opacity-100 text-base text-red-400 hover:text-red-500 transition px-3 py-1 rounded-lg hover:bg-red-50"
            >
              删除
            </button>
          </div>
        </div>

        <p class="text-ink-700 text-lg whitespace-pre-wrap line-clamp-5 leading-relaxed font-serif">{{ entry.content }}</p>

        <div v-if="entry.tags?.length" class="mt-5 flex flex-wrap gap-2.5">
          <span
            v-for="tag in entry.tags" :key="tag.id"
            class="px-4 py-1.5 bg-diary-100/80 text-diary-700 rounded-full text-base"
            :style="tag.color ? { backgroundColor: tag.color + '20', color: tag.color } : {}"
          >
            #{{ tag.tag_name }}
          </span>
        </div>

        <div v-if="entry.AI_ans" class="mt-5 p-5 bg-gradient-to-r from-indigo-50 to-purple-50 rounded-2xl border border-indigo-100/50">
          <p class="text-base text-indigo-400 mb-2 flex items-center gap-1.5">
            <span>🤖</span> 夜记助手总结
          </p>
          <p class="text-lg text-indigo-700 line-clamp-3 leading-relaxed">{{ entry.AI_ans }}</p>
        </div>
      </div>

      <div v-if="hasMore" class="text-center py-8">
        <button @click="loadMore" :disabled="loadingMore"
          class="px-8 py-3 text-diary-600 hover:bg-diary-50 rounded-2xl transition text-lg font-medium">
          {{ loadingMore ? '加载中...' : '加载更多' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { diaryApi } from '@/api/diary'
import { columnApi } from '@/api/column'
import type { DiaryResponse } from '@/types'

defineEmits<{ select: [entry: DiaryResponse] }>()

const entries = ref<DiaryResponse[]>([])
const loading = ref(true)
const loadingMore = ref(false)
const hasMore = ref(true)
const pageSize = 20

onMounted(() => fetchEntries())

async function handleDelete(nid: number) {
  if (!confirm('确定要删除这篇日记吗？')) return
  try {
    await diaryApi.delete(nid)
    entries.value = entries.value.filter(e => e.NID !== nid)
  } catch {}
}

async function handlePublish(nid: number) {
  try {
    await columnApi.publish(nid)
    const entry = entries.value.find(e => e.NID === nid)
    if (entry) entry.published_to_column = true
  } catch (err: any) {
    alert(err.response?.data?.detail || '发布失败')
  }
}

async function handleUnpublish(nid: number) {
  try {
    await columnApi.unpublish(nid)
    const entry = entries.value.find(e => e.NID === nid)
    if (entry) entry.published_to_column = false
  } catch (err: any) {
    alert(err.response?.data?.detail || '下架失败')
  }
}

async function fetchEntries() {
  loading.value = true
  try {
    entries.value = await diaryApi.list(0, pageSize)
    hasMore.value = entries.value.length >= pageSize
  } catch {}
  loading.value = false
}

async function loadMore() {
  loadingMore.value = true
  try {
    const more = await diaryApi.list(entries.value.length, pageSize)
    entries.value.push(...more)
    hasMore.value = more.length >= pageSize
  } catch {}
  loadingMore.value = false
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' })
}

defineExpose({ refresh: fetchEntries })
</script>

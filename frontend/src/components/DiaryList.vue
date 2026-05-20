<template>
  <div>
    <div v-if="loading" class="text-center py-16 text-lg" style="color: var(--text-faint);">
      <span class="text-4xl block mb-3 animate-float">📖</span>加载中...
    </div>

    <div v-else-if="!entries.length" class="text-center py-20">
      <span class="text-5xl block mb-4 animate-float">🌙</span>
      <p class="font-serif text-xl" style="color: var(--text-muted);">还没有日记</p>
      <p class="text-sm mt-2" style="color: var(--text-faint);">写下今天的第一篇吧</p>
    </div>

    <div v-else class="space-y-4">
      <div
        v-for="entry in entries" :key="entry.NID"
        @click="$emit('select', entry)"
        class="group glass-card rounded-2xl p-6 cursor-pointer"
      >
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2.5">
            <span class="text-sm px-3 py-1 rounded-full" style="color: var(--text-muted); background: var(--accent-soft);">{{ formatDate(entry.create_time) }}</span>
            <span v-if="entry.is_open" class="text-xs px-2.5 py-0.5 rounded-full" style="color: var(--accent); background: var(--accent-soft);">公开</span>
            <span v-else class="text-xs px-2.5 py-0.5 rounded-full" style="color: var(--text-faint); background: var(--bg-input);">私密</span>
          </div>
          <div class="flex items-center gap-2">
            <span v-if="entry.weather" class="text-sm" style="color: var(--text-faint);">{{ entry.weather }}</span>
            <button
              @click.stop="$emit('edit', entry)"
              class="opacity-0 group-hover:opacity-100 text-sm transition px-2 py-1 rounded-lg"
              style="color: var(--accent);"
            >编辑</button>
            <button
              v-if="entry.is_open && !entry.published_to_column"
              @click.stop="handlePublish(entry.NID)"
              class="opacity-0 group-hover:opacity-100 text-sm transition px-2 py-1 rounded-lg"
              style="color: var(--accent);"
            >发布专栏</button>
            <button
              v-if="entry.published_to_column"
              @click.stop="handleUnpublish(entry.NID)"
              class="opacity-0 group-hover:opacity-100 text-sm text-amber-500 transition px-2 py-1 rounded-lg"
            >下架专栏</button>
            <button
              @click.stop="handleDelete(entry.NID)"
              class="opacity-0 group-hover:opacity-100 text-sm text-red-400/70 hover:text-red-500 transition px-2 py-1 rounded-lg"
            >删除</button>
          </div>
        </div>

        <p class="text-base whitespace-pre-wrap line-clamp-4 leading-relaxed font-serif" style="color: var(--text-primary);">{{ entry.content }}</p>

        <div v-if="entry.tags?.length" class="mt-3 flex flex-wrap gap-2">
          <span
            v-for="tag in entry.tags" :key="tag.id"
            class="px-3 py-0.5 rounded-full text-xs"
            :style="tag.color
              ? { backgroundColor: tag.color + '18', color: tag.color }
              : { backgroundColor: 'var(--accent-soft)', color: 'var(--accent)' }"
          >#{{ tag.tag_name }}</span>
        </div>

        <!-- AI 总结 — 默认折叠，点击展开 -->
        <div v-if="entry.AI_ans" class="mt-3">
          <button
            @click.stop="toggleAiExpand(entry.NID)"
            class="flex items-center gap-1.5 text-xs transition"
            style="color: var(--text-faint);"
          >
            <span>✨</span>
            <span>AI 总结</span>
            <span>{{ expandedAi.has(entry.NID) ? '▲' : '▼' }}</span>
          </button>
          <div v-if="expandedAi.has(entry.NID)" class="ai-response-card mt-2 p-4 rounded-xl">
            <p class="text-sm leading-relaxed" style="color: var(--text-secondary);">{{ entry.AI_ans }}</p>
          </div>
        </div>
      </div>

      <div v-if="hasMore" class="text-center py-6">
        <button @click="loadMore" :disabled="loadingMore"
          class="px-6 py-2.5 rounded-xl transition text-sm font-medium border"
          style="color: var(--accent); border-color: var(--border-hover); background: var(--accent-soft);">
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

defineEmits<{ select: [entry: DiaryResponse], edit: [entry: DiaryResponse] }>()

const entries = ref<DiaryResponse[]>([])
const loading = ref(true)
const loadingMore = ref(false)
const hasMore = ref(true)
const pageSize = 20
const expandedAi = ref(new Set<number>())

onMounted(() => fetchEntries())

function toggleAiExpand(nid: number) {
  if (expandedAi.value.has(nid)) {
    expandedAi.value.delete(nid)
  } else {
    expandedAi.value.add(nid)
  }
}

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

<template>
  <div class="bg-white/70 backdrop-blur-sm rounded-3xl border border-diary-100 p-10 shadow-sm">
    <div class="flex items-center justify-between mb-8">
      <div class="flex items-center gap-3">
        <span class="text-3xl">📖</span>
        <h2 class="text-2xl font-semibold text-ink-700 font-serif">{{ detail.author_name }} 的日记</h2>
      </div>
      <button @click="$emit('close')" class="text-ink-300 hover:text-ink-500 transition text-2xl">✕</button>
    </div>

    <!-- 元信息 -->
    <div class="flex flex-wrap items-center gap-4 mb-6 text-base text-ink-400">
      <span class="bg-diary-50 px-4 py-2 rounded-full">{{ formatTime(detail.publish_time) }}</span>
      <span v-if="detail.date" class="bg-diary-50 px-4 py-2 rounded-full">📅 {{ detail.date }}</span>
      <span v-if="detail.weather" class="bg-diary-50 px-4 py-2 rounded-full">{{ detail.weather }}</span>
    </div>

    <!-- 正文 -->
    <div class="p-6 bg-diary-50/60 rounded-2xl border border-diary-100 mb-8">
      <p class="text-ink-700 text-lg whitespace-pre-wrap leading-relaxed font-serif">{{ detail.content }}</p>
    </div>

    <!-- 标签 -->
    <div v-if="detail.tags?.length" class="flex flex-wrap gap-2.5">
      <span
        v-for="tag in detail.tags" :key="tag.id"
        class="px-4 py-1.5 bg-diary-100/80 text-diary-700 rounded-full text-base"
        :style="tag.color ? { backgroundColor: tag.color + '20', color: tag.color } : {}"
      >
        #{{ tag.tag_name }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PublicDiaryDetail } from '@/types'

defineProps<{ detail: PublicDiaryDetail }>()
defineEmits<{ close: [] }>()

function formatTime(timeStr: string) {
  if (!timeStr) return ''
  const d = new Date(timeStr)
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' })
}
</script>

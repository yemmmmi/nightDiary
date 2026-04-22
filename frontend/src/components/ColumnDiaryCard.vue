<template>
  <div
    @click="$emit('click', entry)"
    class="group bg-white/70 backdrop-blur-sm rounded-3xl border border-diary-100 p-8 hover:shadow-lg hover:shadow-diary-200/40 hover:border-diary-200 transition-all cursor-pointer"
  >
    <div class="flex items-center justify-between mb-5">
      <span class="text-base text-ink-400 bg-diary-50 px-4 py-2 rounded-full">{{ formatTime(entry.publish_time) }}</span>
      <span class="text-base text-diary-600 font-medium">{{ entry.author_name }}</span>
    </div>

    <p class="text-ink-700 text-lg whitespace-pre-wrap line-clamp-5 leading-relaxed font-serif">{{ entry.content_summary }}</p>

    <div v-if="entry.tags?.length" class="mt-5 flex flex-wrap gap-2.5">
      <span
        v-for="tag in entry.tags" :key="tag.id"
        class="px-4 py-1.5 bg-diary-100/80 text-diary-700 rounded-full text-base"
        :style="tag.color ? { backgroundColor: tag.color + '20', color: tag.color } : {}"
      >
        #{{ tag.tag_name }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PublicDiaryListItem } from '@/types'

defineProps<{ entry: PublicDiaryListItem }>()
defineEmits<{ click: [entry: PublicDiaryListItem] }>()

function formatTime(timeStr: string) {
  if (!timeStr) return ''
  const d = new Date(timeStr)
  return d.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' })
}
</script>

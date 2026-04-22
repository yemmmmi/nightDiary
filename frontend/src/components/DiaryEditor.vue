<template>
  <div class="bg-white/70 backdrop-blur-sm rounded-3xl border border-diary-100 p-10 shadow-sm">
    <div class="flex items-center gap-4 mb-6">
      <span class="text-3xl">✍️</span>
      <h2 class="text-2xl font-semibold text-ink-700 font-serif">写日记</h2>
    </div>

    <form @submit.prevent="handleSubmit">
      <textarea
        v-model="content" rows="6"
        placeholder="今天发生了什么？记录下来吧..."
        class="w-full px-6 py-5 text-lg bg-diary-50/40 border border-diary-200 rounded-2xl resize-none focus:ring-2 focus:ring-diary-400 focus:border-transparent outline-none transition placeholder:text-ink-300 font-serif leading-relaxed"
      />

      <div v-if="tags.length" class="mt-5 flex flex-wrap gap-3">
        <button
          v-for="tag in tags" :key="tag.id" type="button" @click="toggleTag(tag.id)"
          :class="[
            'px-5 py-2 rounded-full text-base font-medium transition border',
            selectedTags.has(tag.id)
              ? 'bg-diary-100 text-diary-700 border-diary-300'
              : 'bg-white text-ink-400 border-diary-100 hover:border-diary-200'
          ]"
        >
          #{{ tag.tag_name }}
        </button>
      </div>

      <div class="mt-6 flex items-center justify-between">
        <div class="flex items-center gap-6">
          <span class="text-base text-ink-300">{{ content.trim().length }} 字</span>
          <label class="flex items-center gap-2 cursor-pointer select-none">
            <input type="checkbox" v-model="isPublic" class="sr-only peer" />
            <div class="w-10 h-6 bg-ink-200 rounded-full peer-checked:bg-diary-500 transition relative">
              <div class="absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition peer-checked:translate-x-4" :class="isPublic ? 'translate-x-4' : ''"></div>
            </div>
            <span class="text-base" :class="isPublic ? 'text-diary-600' : 'text-ink-400'">{{ isPublic ? '公开' : '私密' }}</span>
          </label>
        </div>
        <button
          type="submit" :disabled="!content.trim() || submitting"
          class="px-10 py-4 bg-gradient-to-r from-diary-500 to-diary-600 text-white rounded-2xl text-lg font-semibold hover:from-diary-600 hover:to-diary-700 disabled:opacity-40 disabled:cursor-not-allowed transition shadow-md shadow-diary-200/50"
        >
          {{ submitting ? '发布中...' : '📝 发布日记' }}
        </button>
      </div>

      <p v-if="error" class="mt-4 text-red-500 text-base bg-red-50 px-5 py-3 rounded-xl">{{ error }}</p>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { diaryApi } from '@/api/diary'
import { tagsApi } from '@/api/tags'
import type { TagResponse } from '@/types'

const emit = defineEmits<{ created: [] }>()
const content = ref('')
const tags = ref<TagResponse[]>([])
const selectedTags = ref(new Set<number>())
const submitting = ref(false)
const isPublic = ref(false)
const error = ref('')

onMounted(async () => {
  try { tags.value = await tagsApi.list() } catch {}
})

function toggleTag(id: number) {
  if (selectedTags.value.has(id)) selectedTags.value.delete(id)
  else selectedTags.value.add(id)
}

async function handleSubmit() {
  if (!content.value.trim()) return
  error.value = ''
  submitting.value = true
  try {
    await diaryApi.create({ content: content.value, is_public: isPublic.value, tag_ids: [...selectedTags.value] })
    content.value = ''
    selectedTags.value.clear()
    emit('created')
  } catch (err: any) {
    error.value = err.response?.data?.detail || '发布失败'
  } finally { submitting.value = false }
}
</script>

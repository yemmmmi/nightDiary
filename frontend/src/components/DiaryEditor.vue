<template>
  <div class="glass-card rounded-3xl p-8">
    <div class="flex items-center justify-between mb-5">
      <div class="flex items-center gap-3">
        <span class="text-2xl">{{ editingEntry ? '📝' : '✍️' }}</span>
        <h2 class="text-xl font-semibold font-serif" style="color: var(--text-primary);">{{ editingEntry ? '编辑日记' : '写日记' }}</h2>
      </div>
      <button v-if="editingEntry" @click="cancelEdit"
        class="text-sm px-3 py-1.5 rounded-lg transition"
        style="color: var(--text-muted); background: var(--bg-input);">
        取消编辑
      </button>
    </div>

    <form @submit.prevent="handleSubmit">
      <textarea
        v-model="content" rows="5"
        :placeholder="editingEntry ? '修改日记内容...' : '今天发生了什么？记录下来吧...'"
        class="input-theme resize-none font-serif leading-relaxed"
        style="min-height: 140px; border-radius: 1rem; padding: 1.25rem;"
      />

      <div v-if="tags.length" class="mt-4 flex flex-wrap gap-2">
        <button
          v-for="tag in tags" :key="tag.id" type="button" @click="toggleTag(tag.id)"
          class="px-4 py-1.5 rounded-full text-sm font-medium transition border"
          :style="selectedTags.has(tag.id)
            ? { background: 'var(--accent-soft)', color: 'var(--accent)', borderColor: 'var(--border-hover)' }
            : { background: 'var(--bg-input)', color: 'var(--text-muted)', borderColor: 'var(--border-base)' }"
        >
          #{{ tag.tag_name }}
        </button>
      </div>

      <div class="mt-5 flex items-center justify-between">
        <div class="flex items-center gap-5">
          <span class="text-sm" style="color: var(--text-faint);">{{ content.trim().length }} 字</span>
          <label class="flex items-center gap-2 cursor-pointer select-none">
            <input type="checkbox" v-model="isPublic" class="sr-only peer" />
            <div class="w-9 h-5 rounded-full transition relative" style="background: var(--border-base);"
                 :style="isPublic ? { background: 'var(--accent)' } : {}">
              <div class="absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition"
                   :class="isPublic ? 'translate-x-4' : ''"></div>
            </div>
            <span class="text-sm" :style="{ color: isPublic ? 'var(--accent)' : 'var(--text-muted)' }">{{ isPublic ? '公开' : '私密' }}</span>
          </label>
        </div>
        <button type="submit" :disabled="!content.trim() || submitting" class="px-8 py-3 btn-primary text-base">
          {{ submitting ? (editingEntry ? '保存中...' : '发布中...') : (editingEntry ? '💾 保存修改' : '📝 发布日记') }}
        </button>
      </div>

      <p v-if="error" class="mt-4 text-red-500 text-sm px-4 py-2.5 rounded-xl" style="background: rgba(239,68,68,0.08);">{{ error }}</p>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { diaryApi } from '@/api/diary'
import { tagsApi } from '@/api/tags'
import type { TagResponse, DiaryResponse } from '@/types'

const props = defineProps<{ editEntry?: DiaryResponse | null }>()
const emit = defineEmits<{ created: [], editing: [], updated: [] }>()

let editingDebounceTimer: ReturnType<typeof setTimeout> | null = null
let lastEmittedLength = 0
const content = ref('')
const tags = ref<TagResponse[]>([])
const selectedTags = ref(new Set<number>())
const submitting = ref(false)
const isPublic = ref(false)
const error = ref('')
const editingEntry = ref<DiaryResponse | null>(null)

onMounted(async () => {
  try { tags.value = await tagsApi.list() } catch {}
})

// 监听外部传入的编辑条目
watch(() => props.editEntry, (entry) => {
  if (entry) {
    editingEntry.value = entry
    content.value = entry.content || ''
    isPublic.value = entry.is_open || false
    selectedTags.value = new Set(entry.tags?.map(t => t.id) || [])
  }
}, { immediate: true })

watch(content, (newVal) => {
  if (!editingEntry.value && newVal.length > lastEmittedLength) {
    if (editingDebounceTimer) clearTimeout(editingDebounceTimer)
    editingDebounceTimer = setTimeout(() => {
      emit('editing')
      lastEmittedLength = newVal.length
    }, 1000)
  }
  if (newVal.length === 0) lastEmittedLength = 0
})

function toggleTag(id: number) {
  if (selectedTags.value.has(id)) selectedTags.value.delete(id)
  else selectedTags.value.add(id)
}

function cancelEdit() {
  editingEntry.value = null
  content.value = ''
  selectedTags.value.clear()
  isPublic.value = false
  error.value = ''
  emit('updated') // 通知父组件退出编辑模式
}

async function handleSubmit() {
  if (!content.value.trim()) return
  error.value = ''
  submitting.value = true

  try {
    if (editingEntry.value) {
      // 编辑模式 — 更新日记
      await diaryApi.update(editingEntry.value.NID, {
        content: content.value,
        is_open: isPublic.value,
        tag_ids: [...selectedTags.value],
      })
      editingEntry.value = null
      content.value = ''
      selectedTags.value.clear()
      isPublic.value = false
      emit('updated')
    } else {
      // 新建模式
      await diaryApi.create({ content: content.value, is_public: isPublic.value, tag_ids: [...selectedTags.value] })
      content.value = ''
      selectedTags.value.clear()
      emit('created')
    }
  } catch (err: any) {
    error.value = err.response?.data?.detail || (editingEntry.value ? '保存失败' : '发布失败')
  } finally { submitting.value = false }
}
</script>

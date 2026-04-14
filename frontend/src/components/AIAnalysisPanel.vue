<template>
  <div v-if="entry" class="bg-white/70 backdrop-blur-sm rounded-3xl border border-diary-100 p-10 shadow-sm">
    <div class="flex items-center justify-between mb-8">
      <div class="flex items-center gap-3">
        <span class="text-3xl">🤖</span>
        <h2 class="text-2xl font-semibold text-ink-700 font-serif">AI 总结</h2>
      </div>
      <button @click="$emit('close')" class="text-ink-300 hover:text-ink-500 transition text-2xl">✕</button>
    </div>

    <!-- 日记预览 -->
    <div class="p-6 bg-diary-50/60 rounded-2xl border border-diary-100 mb-8">
      <p class="text-base text-ink-400 mb-3">{{ formatDate(entry.create_time) }}</p>
      <p class="text-ink-600 text-lg whitespace-pre-wrap line-clamp-8 leading-relaxed font-serif">{{ entry.content }}</p>
    </div>

    <!-- AI 回应（从 analysis 的 thk_log 或 entry 的 AI_ans 获取） -->
    <div v-if="aiContent" class="p-8 bg-gradient-to-br from-indigo-50 to-purple-50 rounded-2xl border border-indigo-100/50 mb-8">
      <p class="text-base text-indigo-400 mb-4 font-medium flex items-center gap-2">
        <span>✨</span> 夜记助手的回应
      </p>
      <p class="text-indigo-800 text-lg whitespace-pre-wrap leading-relaxed font-serif">{{ aiContent }}</p>
    </div>

    <!-- Token 消耗明细 -->
    <div v-if="analysis" class="mb-8">
      <button
        @click="showTokenDetail = !showTokenDetail"
        class="flex items-center gap-2 text-base text-ink-400 hover:text-ink-600 transition cursor-pointer"
      >
        <span>🪙 Token: {{ analysis.Token_cost ?? 0 }}</span>
        <span class="text-xs">{{ showTokenDetail ? '▲ 收起' : '▼ 明细' }}</span>
        <span class="ml-4 text-ink-300">{{ analysis.Thk_time ? formatDate(analysis.Thk_time) : '' }}</span>
      </button>
      <div v-if="showTokenDetail" class="mt-3 p-4 bg-diary-50/60 rounded-xl border border-diary-100 text-sm space-y-2">
        <div class="flex justify-between">
          <span class="text-ink-500">缓存命中（免费）</span>
          <span class="text-green-600 font-medium">{{ analysis.cache_hit_tokens ?? 0 }} tokens</span>
        </div>
        <div class="flex justify-between">
          <span class="text-ink-500">输入（付费）</span>
          <span class="text-orange-600 font-medium">{{ analysis.cache_miss_tokens ?? 0 }} tokens</span>
        </div>
        <div class="flex justify-between">
          <span class="text-ink-500">输出（付费）</span>
          <span class="text-orange-600 font-medium">{{ analysis.output_tokens ?? 0 }} tokens</span>
        </div>
        <div class="border-t border-diary-200 pt-2 flex justify-between font-medium">
          <span class="text-ink-600">总计</span>
          <span class="text-ink-700">{{ analysis.Token_cost ?? 0 }} tokens</span>
        </div>
        <div class="border-t border-diary-200 pt-2 flex justify-between text-xs">
          <span class="text-green-600">免费: {{ analysis.cache_hit_tokens ?? 0 }}</span>
          <span class="text-orange-600">付费: {{ (analysis.cache_miss_tokens ?? 0) + (analysis.output_tokens ?? 0) }}</span>
        </div>
      </div>
    </div>

    <!-- 操作 -->
    <div class="flex gap-5">
      <button
        v-if="!analysis" @click="handleCreate" :disabled="loading"
        class="flex-1 py-4 bg-gradient-to-r from-indigo-500 to-purple-500 text-white rounded-2xl text-lg font-semibold hover:from-indigo-600 hover:to-purple-600 disabled:opacity-50 transition shadow-md shadow-indigo-200/50"
      >
        {{ loading ? '✨ 总结中...' : '✨ 获取 AI 总结' }}
      </button>
      <button
        v-else @click="handleUpdate" :disabled="loading"
        class="flex-1 py-4 bg-indigo-50 text-indigo-600 rounded-2xl text-lg font-medium hover:bg-indigo-100 disabled:opacity-50 transition border border-indigo-100"
      >
        {{ loading ? '重新总结中...' : '🔄 重新总结' }}
      </button>
    </div>

    <p v-if="error" class="mt-5 text-red-500 text-lg bg-red-50 px-5 py-3 rounded-xl">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { analysisApi } from '@/api/analysis'
import type { DiaryResponse, AnalysisResponse } from '@/types'

const props = defineProps<{ entry: DiaryResponse | null }>()
const emit = defineEmits<{ close: [] }>()

const analysis = ref<AnalysisResponse | null>(null)
const loading = ref(false)
const error = ref('')
const localAiAns = ref<string | null>(null)
const showTokenDetail = ref(false)

// 显示的 AI 内容：优先本地缓存 > entry 自带的 AI_ans
const aiContent = computed(() => localAiAns.value || props.entry?.AI_ans || null)

watch(() => props.entry, async (e) => {
  analysis.value = null
  error.value = ''
  localAiAns.value = null
  showTokenDetail.value = false
  if (!e) return
  try {
    analysis.value = await analysisApi.get(e.NID)
    // 有分析记录时，重新获取日记拿最新的 AI_ans
    if (analysis.value) {
      await refreshAiAns()
    }
  } catch {}
}, { immediate: true })

async function handleCreate() {
  if (!props.entry) return
  loading.value = true; error.value = ''
  try {
    analysis.value = await analysisApi.create(props.entry.NID)
    // 创建成功后，从 analysis 的 thk_log 中提取 AI 回应不太合适
    // 实际 AI 回应写入了 diary 的 AI_ans 字段，需要重新获取日记
    // 这里用一个简单方案：重新请求日记获取 AI_ans
    await refreshAiAns()
  } catch (err: any) {
    error.value = err.response?.status === 503 ? 'AI 服务暂时不可用' : (err.response?.data?.detail || '总结失败')
  } finally { loading.value = false }
}

async function handleUpdate() {
  if (!props.entry) return
  loading.value = true; error.value = ''
  try {
    analysis.value = await analysisApi.update(props.entry.NID)
    await refreshAiAns()
  } catch (err: any) {
    const d = err.response?.data?.detail || ''
    error.value = d.includes('未变化') ? '日记内容未变化，无需重新总结' : err.response?.status === 503 ? 'AI 服务暂时不可用' : (d || '重新总结失败')
  } finally { loading.value = false }
}

async function refreshAiAns() {
  if (!props.entry) return
  try {
    const { diaryApi } = await import('@/api/diary')
    const updated = await diaryApi.get(props.entry.NID)
    localAiAns.value = updated.AI_ans
  } catch {}
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' })
}
</script>

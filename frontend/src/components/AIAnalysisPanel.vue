<template>
  <div v-if="entry" class="glass-card rounded-3xl p-8">
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-2.5">
        <span class="text-2xl">✨</span>
        <h2 class="text-xl font-semibold font-serif" style="color: var(--text-primary);">AI 总结</h2>
      </div>
      <button @click="$emit('close')" class="w-8 h-8 flex items-center justify-center rounded-lg transition text-xl"
              style="color: var(--text-faint);" @mouseenter="($event.target as HTMLElement).style.color = 'var(--text-secondary)'"
              @mouseleave="($event.target as HTMLElement).style.color = 'var(--text-faint)'">✕</button>
    </div>

    <!-- 日记预览 -->
    <div class="p-5 rounded-2xl border mb-6" style="background: var(--bg-input); border-color: var(--border-base);">
      <p class="text-xs mb-2" style="color: var(--text-faint);">{{ formatDate(entry.create_time) }}</p>
      <p class="text-sm whitespace-pre-wrap line-clamp-6 leading-relaxed font-serif" style="color: var(--text-secondary);">{{ entry.content }}</p>
    </div>

    <!-- AI 回应 -->
    <div v-if="aiContent" ref="aiResponseEl" class="ai-response-card p-6 rounded-2xl mb-6">
      <p class="ai-label text-xs mb-3 font-medium flex items-center gap-1.5">
        <span>✨</span> 夜记助手的回应
      </p>
      <p class="text-base whitespace-pre-wrap leading-relaxed font-serif" style="color: var(--text-primary);">{{ aiContent }}</p>
      <div class="mt-4 pt-3" style="border-top: 1px solid var(--ai-border);">
        <FeedbackButtons :diary-nid="entry!.NID" response-style="empathetic" />
      </div>
    </div>

    <!-- Token 消耗明细 -->
    <div v-if="analysis" class="mb-6">
      <button @click="showTokenDetail = !showTokenDetail"
        class="flex items-center gap-2 text-sm transition cursor-pointer" style="color: var(--text-muted);">
        <span>🪙 Token: {{ analysis.Token_cost ?? 0 }}</span>
        <span class="text-xs">{{ showTokenDetail ? '▲ 收起' : '▼ 明细' }}</span>
        <span class="ml-3" style="color: var(--text-faint);">{{ analysis.Thk_time ? formatDate(analysis.Thk_time) : '' }}</span>
      </button>
      <div v-if="showTokenDetail" class="mt-3 p-4 rounded-xl border text-sm space-y-2" style="background: var(--bg-input); border-color: var(--border-base);">
        <div class="flex justify-between">
          <span style="color: var(--text-muted);">缓存命中（免费）</span>
          <span class="text-green-500 font-medium">{{ analysis.cache_hit_tokens ?? 0 }} tokens</span>
        </div>
        <div class="flex justify-between">
          <span style="color: var(--text-muted);">输入（付费）</span>
          <span class="text-orange-500 font-medium">{{ analysis.cache_miss_tokens ?? 0 }} tokens</span>
        </div>
        <div class="flex justify-between">
          <span style="color: var(--text-muted);">输出（付费）</span>
          <span class="text-orange-500 font-medium">{{ analysis.output_tokens ?? 0 }} tokens</span>
        </div>
        <div class="pt-2 flex justify-between font-medium" style="border-top: 1px solid var(--border-base);">
          <span style="color: var(--text-secondary);">总计</span>
          <span style="color: var(--text-primary);">{{ analysis.Token_cost ?? 0 }} tokens</span>
        </div>
        <div class="pt-2 flex justify-between text-xs" style="border-top: 1px solid var(--border-base);">
          <span class="text-green-500">免费: {{ analysis.cache_hit_tokens ?? 0 }}</span>
          <span class="text-orange-500">付费: {{ (analysis.cache_miss_tokens ?? 0) + (analysis.output_tokens ?? 0) }}</span>
        </div>
      </div>
    </div>

    <!-- 操作 -->
    <div class="flex gap-4">
      <button v-if="!analysis" @click="handleCreate" :disabled="loading" class="flex-1 py-3.5 btn-primary text-base">
        {{ loading ? '✨ 总结中...' : '✨ 获取 AI 总结' }}
      </button>
      <button v-else @click="handleUpdate" :disabled="loading"
        class="flex-1 py-3.5 rounded-2xl text-base font-medium transition border"
        style="background: var(--bg-input); color: var(--text-secondary); border-color: var(--border-base);">
        {{ loading ? '重新总结中...' : '🔄 重新总结' }}
      </button>
    </div>

    <p v-if="error" class="mt-4 text-red-500 text-sm px-4 py-2.5 rounded-xl" style="background: rgba(239,68,68,0.08);">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { analysisApi } from '@/api/analysis'
import { useImplicitFeedback } from '@/composables/useImplicitFeedback'
import type { DiaryResponse, AnalysisResponse } from '@/types'
import FeedbackButtons from './FeedbackButtons.vue'

const props = defineProps<{ entry: DiaryResponse | null }>()
defineEmits<{ close: [] }>()

const analysis = ref<AnalysisResponse | null>(null)
const loading = ref(false)
const error = ref('')
const localAiAns = ref<string | null>(null)
const showTokenDetail = ref(false)
const aiResponseEl = ref<HTMLElement | null>(null)

const currentNid = computed(() => props.entry?.NID ?? null)
const { observeReadComplete, markAiResponseReceived, notifyEditing, checkFrequentUsage } = useImplicitFeedback({
  diaryNid: currentNid,
})

const aiContent = computed(() => localAiAns.value || props.entry?.AI_ans || null)

watch(() => props.entry, async (e) => {
  analysis.value = null
  error.value = ''
  localAiAns.value = null
  showTokenDetail.value = false
  if (!e) return
  try {
    analysis.value = await analysisApi.get(e.NID)
    if (analysis.value) {
      await refreshAiAns()
      await nextTick()
      observeReadComplete(aiResponseEl.value)
    }
  } catch {}
}, { immediate: true })

async function handleCreate() {
  if (!props.entry) return
  loading.value = true; error.value = ''
  checkFrequentUsage(props.entry.NID)
  try {
    analysis.value = await analysisApi.create(props.entry.NID)
    await refreshAiAns()
    markAiResponseReceived()
    await nextTick()
    observeReadComplete(aiResponseEl.value)
  } catch (err: any) {
    error.value = err.response?.status === 503 ? 'AI 服务暂时不可用' : (err.response?.data?.detail || '总结失败')
  } finally { loading.value = false }
}

async function handleUpdate() {
  if (!props.entry) return
  loading.value = true; error.value = ''
  checkFrequentUsage(props.entry.NID)
  try {
    analysis.value = await analysisApi.update(props.entry.NID)
    await refreshAiAns()
    markAiResponseReceived()
    await nextTick()
    observeReadComplete(aiResponseEl.value)
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

defineExpose({ notifyEditing })
</script>

<template>
  <div class="flex items-center gap-3">
    <!-- 已提交确认 -->
    <transition name="fade">
      <span v-if="submitted" class="text-sm text-green-600 font-medium">✓ 已提交</span>
    </transition>

    <!-- 点赞/点踩按钮 -->
    <template v-if="!submitted">
      <button
        @click="handleThumbUp"
        :disabled="loading"
        class="p-2 rounded-lg text-lg transition hover:bg-green-50 hover:scale-110 disabled:opacity-50"
        :class="{ 'bg-green-100 ring-1 ring-green-300': selectedType === 'positive' }"
        title="有帮助"
      >
        👍
      </button>
      <button
        @click="handleThumbDown"
        :disabled="loading"
        class="p-2 rounded-lg text-lg transition hover:bg-red-50 hover:scale-110 disabled:opacity-50"
        :class="{ 'bg-red-100 ring-1 ring-red-300': selectedType === 'negative' }"
        title="需改进"
      >
        👎
      </button>
    </template>

    <!-- 原因选择器（点踩后显示） -->
    <transition name="slide">
      <div v-if="showReasons" class="flex flex-wrap gap-2 ml-2">
        <button
          v-for="reason in reasons"
          :key="reason.value"
          @click="submitWithReason(reason.value)"
          :disabled="loading"
          class="px-3 py-1 text-sm rounded-full border transition disabled:opacity-50"
          :class="[
            selectedReason === reason.value
              ? 'bg-red-50 border-red-300 text-red-700'
              : 'border-ink-200 text-ink-500 hover:border-red-300 hover:bg-red-50 hover:text-red-600'
          ]"
        >
          {{ reason.label }}
        </button>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { feedbackApi } from '@/api/feedback'

const props = defineProps<{
  diaryNid: number
  responseStyle?: string
}>()

const reasons = [
  { value: 'too_long', label: '太长' },
  { value: 'too_short', label: '太短' },
  { value: 'irrelevant', label: '不相关' },
  { value: 'too_generic', label: '太笼统' },
  { value: 'lacks_suggestion', label: '缺乏建议' },
]

const loading = ref(false)
const submitted = ref(false)
const showReasons = ref(false)
const selectedType = ref<'positive' | 'negative' | null>(null)
const selectedReason = ref<string | null>(null)

async function handleThumbUp() {
  selectedType.value = 'positive'
  showReasons.value = false
  loading.value = true
  try {
    await feedbackApi.submitExplicit({
      diary_nid: props.diaryNid,
      response_style: props.responseStyle || 'empathetic',
      feedback_type: 'positive',
    })
    submitted.value = true
    autoHideConfirmation()
  } catch {
    // 静默失败，不阻塞用户体验
  } finally {
    loading.value = false
  }
}

function handleThumbDown() {
  selectedType.value = 'negative'
  showReasons.value = true
}

async function submitWithReason(reason: string) {
  selectedReason.value = reason
  loading.value = true
  try {
    await feedbackApi.submitExplicit({
      diary_nid: props.diaryNid,
      response_style: props.responseStyle || 'empathetic',
      feedback_type: 'negative',
      reason,
    })
    submitted.value = true
    showReasons.value = false
    autoHideConfirmation()
  } catch {
    // 静默失败
  } finally {
    loading.value = false
  }
}

function autoHideConfirmation() {
  setTimeout(() => {
    submitted.value = false
    selectedType.value = null
    selectedReason.value = null
  }, 3000)
}
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateX(-8px);
}
</style>

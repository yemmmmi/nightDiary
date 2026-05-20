/**
 * 隐式反馈信号采集 Composable
 * ============================
 *
 * 采集三种隐式反馈信号并提交到后端：
 * - read_complete: 用户完整阅读 AI 回应（通过 IntersectionObserver 检测）
 * - inspired_writing: 收到 AI 回应后 5 分钟内继续编辑日记
 * - frequent_usage: 24 小时内再次触发 AI 分析
 *
 * 所有信号以 fire-and-forget 方式提交，不阻塞 UI，静默处理错误。
 */

import { ref, onUnmounted, type Ref } from 'vue'
import http from '@/api/http'

// ─── Constants ──────────────────────────────────────────────────────────────

const INSPIRED_WRITING_WINDOW_MS = 5 * 60 * 1000 // 5 分钟
const FREQUENT_USAGE_WINDOW_MS = 24 * 60 * 60 * 1000 // 24 小时
const LAST_ANALYSIS_KEY = 'implicit_feedback_last_analysis_ts'

// ─── Types ──────────────────────────────────────────────────────────────────

interface ImplicitFeedbackPayload {
  diary_nid: number
  response_style: string
  signal_type: 'read_complete' | 'inspired_writing' | 'frequent_usage'
}

interface UseImplicitFeedbackOptions {
  /** 当前日记 NID */
  diaryNid: Ref<number | null>
  /** 当前回应使用的风格（默认 empathetic） */
  responseStyle?: Ref<string>
}

// ─── Helper: Fire-and-forget POST ───────────────────────────────────────────

function sendImplicitSignal(payload: ImplicitFeedbackPayload): void {
  http.post('/feedback/implicit', payload).catch(() => {
    // 静默处理错误，不阻塞 UI
  })
}

// ─── Composable ─────────────────────────────────────────────────────────────

export function useImplicitFeedback(options: UseImplicitFeedbackOptions) {
  const { diaryNid, responseStyle } = options
  const defaultStyle = ref('empathetic')

  // 内部状态
  let observer: IntersectionObserver | null = null
  let inspiredWritingTimer: ReturnType<typeof setTimeout> | null = null
  let aiResponseReceivedAt: number | null = null
  let readCompleteSent = false

  // ─── read_complete: IntersectionObserver 检测完整阅读 ─────────────────────

  /**
   * 开始观察 AI 回应容器元素。
   * 当元素完全进入视口（intersectionRatio >= 0.9）时触发 read_complete 信号。
   * 调用方应在 AI 回应渲染后调用此方法，传入回应容器的 DOM 元素。
   */
  function observeReadComplete(el: HTMLElement | null): void {
    // 清理之前的 observer
    stopObserving()
    readCompleteSent = false

    if (!el) return

    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          // 元素 90% 以上可见视为完整阅读
          if (entry.isIntersecting && entry.intersectionRatio >= 0.9) {
            triggerReadComplete()
            stopObserving()
          }
        }
      },
      { threshold: [0.9] }
    )

    observer.observe(el)
  }

  function stopObserving(): void {
    if (observer) {
      observer.disconnect()
      observer = null
    }
  }

  function triggerReadComplete(): void {
    if (readCompleteSent) return
    const nid = diaryNid.value
    if (!nid) return

    readCompleteSent = true
    sendImplicitSignal({
      diary_nid: nid,
      response_style: responseStyle?.value ?? defaultStyle.value,
      signal_type: 'read_complete',
    })
  }

  // ─── inspired_writing: 5 分钟内继续编辑 ──────────────────────────────────

  /**
   * 标记 AI 回应已收到。开始 5 分钟计时窗口。
   * 在此窗口内如果调用 notifyEditing()，将触发 inspired_writing 信号。
   */
  function markAiResponseReceived(): void {
    aiResponseReceivedAt = Date.now()

    // 清理之前的计时器
    if (inspiredWritingTimer) {
      clearTimeout(inspiredWritingTimer)
    }

    // 5 分钟后窗口过期
    inspiredWritingTimer = setTimeout(() => {
      aiResponseReceivedAt = null
      inspiredWritingTimer = null
    }, INSPIRED_WRITING_WINDOW_MS)
  }

  /**
   * 通知用户正在编辑日记内容。
   * 如果在 AI 回应后 5 分钟内调用，触发 inspired_writing 信号（仅触发一次）。
   */
  function notifyEditing(): void {
    if (!aiResponseReceivedAt) return

    const elapsed = Date.now() - aiResponseReceivedAt
    if (elapsed <= INSPIRED_WRITING_WINDOW_MS) {
      const nid = diaryNid.value
      if (!nid) return

      sendImplicitSignal({
        diary_nid: nid,
        response_style: responseStyle?.value ?? defaultStyle.value,
        signal_type: 'inspired_writing',
      })

      // 只触发一次
      aiResponseReceivedAt = null
      if (inspiredWritingTimer) {
        clearTimeout(inspiredWritingTimer)
        inspiredWritingTimer = null
      }
    }
  }

  // ─── frequent_usage: 24 小时内再次触发分析 ────────────────────────────────

  /**
   * 检查并记录分析触发事件。
   * 如果距离上次分析不到 24 小时，触发 frequent_usage 信号。
   * 应在用户点击"获取 AI 总结"或"重新总结"时调用。
   */
  function checkFrequentUsage(nid: number, style?: string): void {
    const now = Date.now()
    const lastTs = localStorage.getItem(LAST_ANALYSIS_KEY)

    if (lastTs) {
      const elapsed = now - parseInt(lastTs, 10)
      if (elapsed <= FREQUENT_USAGE_WINDOW_MS && elapsed > 0) {
        sendImplicitSignal({
          diary_nid: nid,
          response_style: style ?? responseStyle?.value ?? defaultStyle.value,
          signal_type: 'frequent_usage',
        })
      }
    }

    // 更新最后分析时间戳
    localStorage.setItem(LAST_ANALYSIS_KEY, now.toString())
  }

  // ─── Cleanup ──────────────────────────────────────────────────────────────

  function cleanup(): void {
    stopObserving()
    if (inspiredWritingTimer) {
      clearTimeout(inspiredWritingTimer)
      inspiredWritingTimer = null
    }
    aiResponseReceivedAt = null
    readCompleteSent = false
  }

  onUnmounted(cleanup)

  return {
    observeReadComplete,
    markAiResponseReceived,
    notifyEditing,
    checkFrequentUsage,
    cleanup,
  }
}

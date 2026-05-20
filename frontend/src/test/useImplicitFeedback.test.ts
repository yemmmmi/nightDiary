/**
 * 隐式反馈信号采集 Composable 单元测试
 *
 * 验证三种隐式反馈信号的采集逻辑：
 * - read_complete: IntersectionObserver 检测完整阅读
 * - inspired_writing: AI 回应后 5 分钟内继续编辑
 * - frequent_usage: 24 小时内再次触发分析
 *
 * **Validates: Requirements 11.1, 11.2, 11.3**
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { ref } from 'vue'
import { useImplicitFeedback } from '@/composables/useImplicitFeedback'

// Mock http module
vi.mock('@/api/http', () => ({
  default: {
    post: vi.fn(() => Promise.resolve({ data: { success: true, message: 'ok' } })),
  },
}))

// Suppress Vue lifecycle warnings in tests (no component instance)
vi.mock('vue', async () => {
  const actual = await vi.importActual('vue')
  return {
    ...actual,
    onUnmounted: vi.fn(), // no-op in test context
  }
})

let mockObserverInstance: { callback: IntersectionObserverCallback; elements: Element[] } | null = null

describe('useImplicitFeedback', () => {
  let httpPost: ReturnType<typeof vi.fn>

  beforeEach(async () => {
    vi.useFakeTimers()
    localStorage.clear()

    // Get the mocked http module and reset the mock
    const httpModule = await import('@/api/http')
    httpPost = httpModule.default.post as ReturnType<typeof vi.fn>
    httpPost.mockClear()
    httpPost.mockImplementation(() => Promise.resolve({ data: { success: true } }))

    // Setup IntersectionObserver mock
    mockObserverInstance = null
    vi.stubGlobal('IntersectionObserver', class {
      callback: IntersectionObserverCallback
      elements: Element[] = []
      constructor(callback: IntersectionObserverCallback) {
        this.callback = callback
        mockObserverInstance = this as any
      }
      observe(el: Element) { this.elements.push(el) }
      disconnect() { this.elements = [] }
    })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  describe('read_complete 信号', () => {
    it('当 AI 回应元素 90% 以上可见时，应发送 read_complete 信号', () => {
      const diaryNid = ref<number | null>(42)
      const { observeReadComplete } = useImplicitFeedback({ diaryNid })

      const el = document.createElement('div')
      observeReadComplete(el)

      // Simulate intersection with 90%+ visibility
      const observer = mockObserverInstance!
      const entries = [{
        isIntersecting: true,
        intersectionRatio: 0.95,
        target: el,
        boundingClientRect: {} as DOMRectReadOnly,
        intersectionRect: {} as DOMRectReadOnly,
        rootBounds: null,
        time: Date.now(),
      }] as IntersectionObserverEntry[]
      observer.callback(entries, {} as IntersectionObserver)

      expect(httpPost).toHaveBeenCalledWith('/feedback/implicit', {
        diary_nid: 42,
        response_style: 'empathetic',
        signal_type: 'read_complete',
      })
    })

    it('read_complete 信号每次分析只触发一次（去重）', () => {
      const diaryNid = ref<number | null>(42)
      const { observeReadComplete } = useImplicitFeedback({ diaryNid })

      const el = document.createElement('div')
      observeReadComplete(el)

      const observer = mockObserverInstance!
      const entries = [{
        isIntersecting: true,
        intersectionRatio: 0.95,
        target: el,
        boundingClientRect: {} as DOMRectReadOnly,
        intersectionRect: {} as DOMRectReadOnly,
        rootBounds: null,
        time: Date.now(),
      }] as IntersectionObserverEntry[]

      // Trigger twice
      observer.callback(entries, {} as IntersectionObserver)
      observer.callback(entries, {} as IntersectionObserver)

      // Should only be called once
      expect(httpPost).toHaveBeenCalledTimes(1)
    })

    it('当元素可见度不足 90% 时，不应触发 read_complete', () => {
      const diaryNid = ref<number | null>(42)
      const { observeReadComplete } = useImplicitFeedback({ diaryNid })

      const el = document.createElement('div')
      observeReadComplete(el)

      const observer = mockObserverInstance!
      const entries = [{
        isIntersecting: true,
        intersectionRatio: 0.5,
        target: el,
        boundingClientRect: {} as DOMRectReadOnly,
        intersectionRect: {} as DOMRectReadOnly,
        rootBounds: null,
        time: Date.now(),
      }] as IntersectionObserverEntry[]
      observer.callback(entries, {} as IntersectionObserver)

      expect(httpPost).not.toHaveBeenCalled()
    })
  })

  describe('inspired_writing 信号', () => {
    it('AI 回应后 5 分钟内编辑应触发 inspired_writing 信号', () => {
      const diaryNid = ref<number | null>(42)
      const { markAiResponseReceived, notifyEditing } = useImplicitFeedback({ diaryNid })

      markAiResponseReceived()

      // 2 分钟后用户开始编辑
      vi.advanceTimersByTime(2 * 60 * 1000)
      notifyEditing()

      expect(httpPost).toHaveBeenCalledWith('/feedback/implicit', {
        diary_nid: 42,
        response_style: 'empathetic',
        signal_type: 'inspired_writing',
      })
    })

    it('AI 回应后超过 5 分钟编辑不应触发 inspired_writing 信号', () => {
      const diaryNid = ref<number | null>(42)
      const { markAiResponseReceived, notifyEditing } = useImplicitFeedback({ diaryNid })

      markAiResponseReceived()

      // 6 分钟后用户开始编辑（超过窗口）
      vi.advanceTimersByTime(6 * 60 * 1000)
      notifyEditing()

      expect(httpPost).not.toHaveBeenCalled()
    })

    it('inspired_writing 信号只触发一次', () => {
      const diaryNid = ref<number | null>(42)
      const { markAiResponseReceived, notifyEditing } = useImplicitFeedback({ diaryNid })

      markAiResponseReceived()

      // 第一次编辑
      vi.advanceTimersByTime(1 * 60 * 1000)
      notifyEditing()

      // 第二次编辑
      vi.advanceTimersByTime(1 * 60 * 1000)
      notifyEditing()

      expect(httpPost).toHaveBeenCalledTimes(1)
    })
  })

  describe('frequent_usage 信号', () => {
    it('24 小时内再次触发分析应发送 frequent_usage 信号', () => {
      const diaryNid = ref<number | null>(42)
      const { checkFrequentUsage } = useImplicitFeedback({ diaryNid })

      // 第一次分析
      checkFrequentUsage(42)
      expect(httpPost).not.toHaveBeenCalled() // 第一次不触发

      // 12 小时后再次分析
      vi.advanceTimersByTime(12 * 60 * 60 * 1000)
      checkFrequentUsage(42)

      expect(httpPost).toHaveBeenCalledWith('/feedback/implicit', {
        diary_nid: 42,
        response_style: 'empathetic',
        signal_type: 'frequent_usage',
      })
    })

    it('超过 24 小时后再次分析不应触发 frequent_usage 信号', () => {
      const diaryNid = ref<number | null>(42)
      const { checkFrequentUsage } = useImplicitFeedback({ diaryNid })

      // 第一次分析
      checkFrequentUsage(42)

      // 25 小时后再次分析
      vi.advanceTimersByTime(25 * 60 * 60 * 1000)
      checkFrequentUsage(42)

      expect(httpPost).not.toHaveBeenCalled()
    })

    it('frequent_usage 使用 localStorage 持久化时间戳', () => {
      const diaryNid = ref<number | null>(42)
      const { checkFrequentUsage } = useImplicitFeedback({ diaryNid })

      checkFrequentUsage(42)

      const stored = localStorage.getItem('implicit_feedback_last_analysis_ts')
      expect(stored).not.toBeNull()
      expect(parseInt(stored!, 10)).toBeGreaterThan(0)
    })
  })
})

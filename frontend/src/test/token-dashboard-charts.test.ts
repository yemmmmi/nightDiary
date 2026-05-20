/**
 * Token 仪表盘图表与轮询测试
 *
 * 验证：
 * - 折线图正确渲染过去 30 天每日 Token 消耗数据
 * - 饼图正确展示 cache_hit/cache_miss/output_tokens 分布
 * - 饼图支持 7 天/30 天/全部时间范围切换
 * - 每 30 秒轮询 API 获取最新数据
 * - 组件卸载时清理轮询定时器
 *
 * **Validates: Requirements 24.2, 24.3, 24.9**
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import TokenDashboardPage from '@/pages/TokenDashboardPage.vue'
import type { TokenStats, AnalysisHistory } from '@/api/tokenStats'

// Mock vue-chartjs components
vi.mock('vue-chartjs', () => ({
  Line: {
    name: 'Line',
    props: ['data', 'options'],
    template: '<canvas data-testid="line-chart"></canvas>',
  },
  Doughnut: {
    name: 'Doughnut',
    props: ['data', 'options'],
    template: '<canvas data-testid="doughnut-chart"></canvas>',
  },
}))

// Mock chart.js (no-op registration)
vi.mock('chart.js', () => ({
  Chart: { register: vi.fn() },
  CategoryScale: class {},
  LinearScale: class {},
  PointElement: class {},
  LineElement: class {},
  ArcElement: class {},
  Title: class {},
  Tooltip: class {},
  Legend: class {},
  Filler: class {},
}))

// Generate daily stats for testing
function generateDailyStats(days: number) {
  const stats = []
  const now = new Date()
  for (let i = days - 1; i >= 0; i--) {
    const date = new Date(now)
    date.setDate(date.getDate() - i)
    stats.push({
      date: date.toISOString().split('T')[0],
      total_tokens: 1000 + Math.floor(Math.random() * 500),
      cache_hit_tokens: 300 + Math.floor(Math.random() * 200),
      cache_miss_tokens: 400 + Math.floor(Math.random() * 200),
      output_tokens: 300 + Math.floor(Math.random() * 100),
    })
  }
  return stats
}

const mockDailyStats = generateDailyStats(30)

const mockStats: TokenStats = {
  total_tokens: 45000,
  total_paid_tokens: 30000,
  average_tokens_per_analysis: 1500,
  total_analyses: 30,
  estimated_cost: 0.045,
  daily_stats: mockDailyStats,
}

const mockHistory: AnalysisHistory = {
  items: [
    {
      thk_id: 1,
      diary_nid: 101,
      date: '2024-01-15T10:30:00',
      diary_snippet: '今天天气很好',
      total_tokens: 1200,
      cache_hit_tokens: 400,
      cache_miss_tokens: 500,
      output_tokens: 300,
      agent_mode: 'multi_agent',
      activated_agents: 'retrieval,empathy',
    },
  ],
  total: 1,
  page: 1,
  page_size: 20,
}

// Mock the API
const mockGetStats = vi.fn().mockResolvedValue(mockStats)
const mockGetHistory = vi.fn().mockResolvedValue(mockHistory)

vi.mock('@/api/tokenStats', () => ({
  tokenStatsApi: {
    getStats: (...args: any[]) => mockGetStats(...args),
    getHistory: (...args: any[]) => mockGetHistory(...args),
  },
}))

// Router setup
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: { template: '<div />' } },
    { path: '/diary', component: { template: '<div />' } },
    { path: '/tags', component: { template: '<div />' } },
    { path: '/column', component: { template: '<div />' } },
    { path: '/models', component: { template: '<div />' } },
    { path: '/report', component: { template: '<div />' } },
    { path: '/token-dashboard', component: TokenDashboardPage },
    { path: '/profile', component: { template: '<div />' } },
  ],
})

describe('TokenDashboardPage - Charts & Polling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    mockGetStats.mockClear()
    mockGetHistory.mockClear()
    mockGetStats.mockResolvedValue(mockStats)
    mockGetHistory.mockResolvedValue(mockHistory)
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function mountPage() {
    return mount(TokenDashboardPage, {
      global: {
        plugins: [router],
      },
    })
  }

  describe('折线图 (Line Chart)', () => {
    it('应在数据加载后渲染折线图组件', async () => {
      const wrapper = mountPage()
      await flushPromises()

      const lineChart = wrapper.findComponent({ name: 'Line' })
      expect(lineChart.exists()).toBe(true)
    })

    it('折线图数据应包含 30 天的标签和数据点', async () => {
      const wrapper = mountPage()
      await flushPromises()

      const lineChart = wrapper.findComponent({ name: 'Line' })
      const chartData = lineChart.props('data')

      expect(chartData.labels).toHaveLength(30)
      expect(chartData.datasets[0].data).toHaveLength(30)
    })

    it('折线图标签应为 M/D 格式', async () => {
      const wrapper = mountPage()
      await flushPromises()

      const lineChart = wrapper.findComponent({ name: 'Line' })
      const chartData = lineChart.props('data')

      // Each label should match M/D format
      chartData.labels.forEach((label: string) => {
        expect(label).toMatch(/^\d{1,2}\/\d{1,2}$/)
      })
    })
  })

  describe('饼图 (Doughnut Chart)', () => {
    it('应在数据加载后渲染饼图组件', async () => {
      const wrapper = mountPage()
      await flushPromises()

      const doughnut = wrapper.findComponent({ name: 'Doughnut' })
      expect(doughnut.exists()).toBe(true)
    })

    it('饼图应包含三个数据段：缓存命中、付费输入、付费输出', async () => {
      const wrapper = mountPage()
      await flushPromises()

      const doughnut = wrapper.findComponent({ name: 'Doughnut' })
      const chartData = doughnut.props('data')

      expect(chartData.labels).toEqual(['缓存命中（免费）', '付费输入', '付费输出'])
      expect(chartData.datasets[0].data).toHaveLength(3)
    })

    it('应显示时间范围切换按钮（7天/30天/全部）', async () => {
      const wrapper = mountPage()
      await flushPromises()

      const buttons = wrapper.findAll('button').filter((b) => {
        const text = b.text()
        return text === '7 天' || text === '30 天' || text === '全部'
      })
      expect(buttons).toHaveLength(3)
    })

    it('切换到 7 天范围时饼图数据应只包含最近 7 天', async () => {
      const wrapper = mountPage()
      await flushPromises()

      // Click "7 天" button
      const btn7d = wrapper.findAll('button').find((b) => b.text() === '7 天')
      expect(btn7d).toBeDefined()
      await btn7d!.trigger('click')

      const doughnut = wrapper.findComponent({ name: 'Doughnut' })
      const chartData = doughnut.props('data')

      // Calculate expected values from last 7 days of mock data
      const cutoff = new Date()
      cutoff.setDate(cutoff.getDate() - 7)
      const last7Days = mockDailyStats.filter((d) => new Date(d.date) >= cutoff)
      const expectedCacheHit = last7Days.reduce((sum, d) => sum + d.cache_hit_tokens, 0)
      const expectedCacheMiss = last7Days.reduce((sum, d) => sum + d.cache_miss_tokens, 0)
      const expectedOutput = last7Days.reduce((sum, d) => sum + d.output_tokens, 0)

      expect(chartData.datasets[0].data[0]).toBe(expectedCacheHit)
      expect(chartData.datasets[0].data[1]).toBe(expectedCacheMiss)
      expect(chartData.datasets[0].data[2]).toBe(expectedOutput)
    })

    it('切换到全部范围时饼图数据应包含所有数据', async () => {
      const wrapper = mountPage()
      await flushPromises()

      // Click "全部" button
      const btnAll = wrapper.findAll('button').find((b) => b.text() === '全部')
      await btnAll!.trigger('click')

      const doughnut = wrapper.findComponent({ name: 'Doughnut' })
      const chartData = doughnut.props('data')

      const expectedCacheHit = mockDailyStats.reduce((sum, d) => sum + d.cache_hit_tokens, 0)
      const expectedCacheMiss = mockDailyStats.reduce((sum, d) => sum + d.cache_miss_tokens, 0)
      const expectedOutput = mockDailyStats.reduce((sum, d) => sum + d.output_tokens, 0)

      expect(chartData.datasets[0].data[0]).toBe(expectedCacheHit)
      expect(chartData.datasets[0].data[1]).toBe(expectedCacheMiss)
      expect(chartData.datasets[0].data[2]).toBe(expectedOutput)
    })
  })

  describe('数据轮询 (Polling)', () => {
    it('应每 30 秒轮询一次 API', async () => {
      mountPage()
      await flushPromises()

      // Initial fetch
      expect(mockGetStats).toHaveBeenCalledTimes(1)
      expect(mockGetHistory).toHaveBeenCalledTimes(1)

      // Advance 30 seconds
      vi.advanceTimersByTime(30000)
      await flushPromises()

      expect(mockGetStats).toHaveBeenCalledTimes(2)
      expect(mockGetHistory).toHaveBeenCalledTimes(2)

      // Advance another 30 seconds
      vi.advanceTimersByTime(30000)
      await flushPromises()

      expect(mockGetStats).toHaveBeenCalledTimes(3)
      expect(mockGetHistory).toHaveBeenCalledTimes(3)
    })

    it('轮询更新后图表数据应自动刷新', async () => {
      const wrapper = mountPage()
      await flushPromises()

      // Update mock to return different data
      const updatedStats = {
        ...mockStats,
        total_tokens: 99999,
        daily_stats: mockDailyStats.map((d) => ({ ...d, total_tokens: 2000 })),
      }
      mockGetStats.mockResolvedValue(updatedStats)

      // Trigger poll
      vi.advanceTimersByTime(30000)
      await flushPromises()

      // Verify line chart updated
      const lineChart = wrapper.findComponent({ name: 'Line' })
      const chartData = lineChart.props('data')
      expect(chartData.datasets[0].data[0]).toBe(2000)
    })

    it('组件卸载时应清理轮询定时器', async () => {
      const wrapper = mountPage()
      await flushPromises()

      // Unmount
      wrapper.unmount()

      // Advance time - should not trigger additional calls
      vi.advanceTimersByTime(60000)
      await flushPromises()

      // Only the initial call should have been made
      expect(mockGetStats).toHaveBeenCalledTimes(1)
    })

    it('轮询失败时不应显示错误信息（静默失败）', async () => {
      const wrapper = mountPage()
      await flushPromises()

      // Make API fail on next poll
      mockGetStats.mockRejectedValueOnce(new Error('Network error'))

      vi.advanceTimersByTime(30000)
      await flushPromises()

      // Error should not be shown
      expect(wrapper.text()).not.toContain('加载数据失败')
    })
  })
})

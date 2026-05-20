<template>
  <div class="min-h-screen bg-gradient-to-b from-diary-50/60 to-amber-50/40">
    <!-- 顶部导航 -->
    <nav class="sticky top-0 z-30 bg-white/70 backdrop-blur-md border-b border-diary-100">
      <div class="w-full px-4 sm:px-12 py-4 sm:py-6 flex items-center justify-between">
        <div class="flex items-center gap-2 sm:gap-4">
          <span class="text-3xl sm:text-5xl">🌙</span>
          <span class="text-2xl sm:text-4xl font-bold text-ink-800 font-serif">夜记</span>
        </div>
        <div class="hidden md:flex items-center gap-8 text-xl">
          <router-link to="/diary" class="text-ink-500 hover:text-diary-600 transition">日记</router-link>
          <router-link to="/tags" class="text-ink-500 hover:text-diary-600 transition">标签</router-link>
          <router-link to="/column" class="text-ink-500 hover:text-diary-600 transition">专栏</router-link>
          <router-link to="/models" class="text-ink-500 hover:text-diary-600 transition">模型</router-link>
          <router-link to="/report" class="text-ink-500 hover:text-diary-600 transition">报表</router-link>
          <router-link to="/token-dashboard" class="text-diary-600 font-medium transition">Token</router-link>
          <router-link to="/profile" class="text-ink-500 hover:text-diary-600 transition font-medium">个人中心</router-link>
        </div>
        <!-- 移动端菜单按钮 -->
        <button @click="mobileMenuOpen = !mobileMenuOpen" class="md:hidden text-ink-600 text-2xl">
          ☰
        </button>
      </div>
      <!-- 移动端下拉菜单 -->
      <div v-if="mobileMenuOpen" class="md:hidden border-t border-diary-100 bg-white/90 px-4 py-3 space-y-2">
        <router-link to="/diary" class="block text-ink-500 hover:text-diary-600 py-1">日记</router-link>
        <router-link to="/tags" class="block text-ink-500 hover:text-diary-600 py-1">标签</router-link>
        <router-link to="/column" class="block text-ink-500 hover:text-diary-600 py-1">专栏</router-link>
        <router-link to="/models" class="block text-ink-500 hover:text-diary-600 py-1">模型</router-link>
        <router-link to="/report" class="block text-ink-500 hover:text-diary-600 py-1">报表</router-link>
        <router-link to="/token-dashboard" class="block text-diary-600 font-medium py-1">Token 仪表盘</router-link>
        <router-link to="/profile" class="block text-ink-500 hover:text-diary-600 py-1">个人中心</router-link>
      </div>
    </nav>

    <!-- 页面内容 -->
    <div class="w-full px-4 sm:px-12 py-6 sm:py-12">
      <div class="flex items-center justify-between mb-6 sm:mb-8">
        <h1 class="text-xl sm:text-2xl font-bold text-ink-800">Token 消费仪表盘</h1>
        <router-link to="/diary" class="text-sm text-blue-600 hover:underline">← 返回日记</router-link>
      </div>

      <!-- 加载状态 -->
      <div v-if="loading" class="text-center py-16 text-ink-400 text-lg">加载中...</div>

      <!-- 错误状态 -->
      <div v-else-if="error" class="text-center py-16">
        <p class="text-red-500 mb-4">{{ error }}</p>
        <button @click="fetchData" class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm">
          重试
        </button>
      </div>

      <!-- 数据展示 -->
      <div v-else>
        <!-- 统计卡片 -->
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 sm:gap-4 mb-6 sm:mb-8">
          <div class="bg-white rounded-xl shadow-sm p-4 sm:p-5">
            <p class="text-xs sm:text-sm text-ink-400 mb-1">总消耗 Token</p>
            <p class="text-lg sm:text-2xl font-bold text-ink-800">{{ formatNumber(stats.total_tokens) }}</p>
          </div>
          <div class="bg-white rounded-xl shadow-sm p-4 sm:p-5">
            <p class="text-xs sm:text-sm text-ink-400 mb-1">总付费 Token</p>
            <p class="text-lg sm:text-2xl font-bold text-orange-600">{{ formatNumber(stats.total_paid_tokens) }}</p>
          </div>
          <div class="bg-white rounded-xl shadow-sm p-4 sm:p-5">
            <p class="text-xs sm:text-sm text-ink-400 mb-1">平均 Token/次</p>
            <p class="text-lg sm:text-2xl font-bold text-ink-800">{{ formatNumber(Math.round(stats.average_tokens_per_analysis)) }}</p>
          </div>
          <div class="bg-white rounded-xl shadow-sm p-4 sm:p-5">
            <p class="text-xs sm:text-sm text-ink-400 mb-1">总分析次数</p>
            <p class="text-lg sm:text-2xl font-bold text-blue-600">{{ stats.total_analyses }}</p>
          </div>
          <div class="bg-white rounded-xl shadow-sm p-4 sm:p-5 col-span-2 sm:col-span-1">
            <p class="text-xs sm:text-sm text-ink-400 mb-1">预估费用</p>
            <p class="text-lg sm:text-2xl font-bold text-green-600">¥{{ stats.estimated_cost.toFixed(4) }}</p>
          </div>
        </div>

        <!-- 图表区域：桌面端 2 列，移动端单列 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-6 mb-6 sm:mb-8">
          <!-- 折线图 -->
          <div class="bg-white rounded-xl shadow-sm p-5 sm:p-6">
            <h2 class="text-sm font-semibold text-ink-700 mb-4">每日 Token 消耗趋势（近 30 天）</h2>
            <div class="h-48 sm:h-64">
              <Line v-if="lineChartData" :data="lineChartData" :options="lineChartOptions" />
              <div v-else class="h-full flex items-center justify-center text-ink-300 text-sm">
                暂无数据
              </div>
            </div>
          </div>

          <!-- 饼图 -->
          <div class="bg-white rounded-xl shadow-sm p-5 sm:p-6">
            <div class="flex items-center justify-between mb-4">
              <h2 class="text-sm font-semibold text-ink-700">Token 分布</h2>
              <div class="flex gap-1">
                <button
                  v-for="range in pieRangeOptions"
                  :key="range.value"
                  @click="pieRange = range.value"
                  class="px-2 py-0.5 text-xs rounded-md transition"
                  :class="pieRange === range.value
                    ? 'bg-diary-600 text-white'
                    : 'bg-gray-100 text-ink-500 hover:bg-gray-200'"
                >
                  {{ range.label }}
                </button>
              </div>
            </div>
            <div class="h-48 sm:h-64">
              <Doughnut v-if="pieChartData" :data="pieChartData" :options="pieChartOptions" />
              <div v-else class="h-full flex items-center justify-center text-ink-300 text-sm">
                暂无数据
              </div>
            </div>
          </div>
        </div>

        <!-- 分析历史表格：全宽 -->
        <div class="bg-white rounded-xl shadow-sm p-5 sm:p-6">
          <h2 class="text-sm font-semibold text-ink-700 mb-4">分析历史</h2>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead>
                <tr class="border-b border-gray-200 text-left text-ink-500">
                  <th class="pb-3 pr-4 font-medium">日期</th>
                  <th class="pb-3 pr-4 font-medium">日记片段</th>
                  <th class="pb-3 pr-4 font-medium text-right">总 Token</th>
                  <th class="pb-3 pr-4 font-medium text-right hidden sm:table-cell">缓存命中</th>
                  <th class="pb-3 pr-4 font-medium text-right hidden sm:table-cell">付费输入</th>
                  <th class="pb-3 pr-4 font-medium text-right hidden md:table-cell">付费输出</th>
                  <th class="pb-3 font-medium hidden lg:table-cell">模式</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!history.items.length">
                  <td colspan="7" class="py-8 text-center text-ink-300">暂无分析记录</td>
                </tr>
                <tr
                  v-for="item in history.items"
                  :key="item.thk_id"
                  class="border-b border-gray-100 hover:bg-gray-50/50"
                >
                  <td class="py-3 pr-4 text-ink-600 whitespace-nowrap">{{ formatDate(item.date) }}</td>
                  <td class="py-3 pr-4 text-ink-700 max-w-[120px] sm:max-w-[200px] truncate">{{ item.diary_snippet || '—' }}</td>
                  <td class="py-3 pr-4 text-right text-ink-800 font-medium">{{ item.total_tokens ?? '—' }}</td>
                  <td class="py-3 pr-4 text-right text-green-600 hidden sm:table-cell">{{ item.cache_hit_tokens ?? '—' }}</td>
                  <td class="py-3 pr-4 text-right text-orange-600 hidden sm:table-cell">{{ item.cache_miss_tokens ?? '—' }}</td>
                  <td class="py-3 pr-4 text-right text-blue-600 hidden md:table-cell">{{ item.output_tokens ?? '—' }}</td>
                  <td class="py-3 hidden lg:table-cell">
                    <span
                      v-if="item.agent_mode"
                      class="px-2 py-0.5 rounded-full text-xs"
                      :class="agentModeClass(item.agent_mode)"
                    >
                      {{ agentModeLabel(item.agent_mode) }}
                    </span>
                    <span v-else class="text-ink-300">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 分页 -->
          <div v-if="history.total > history.page_size" class="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
            <p class="text-xs text-ink-400">
              共 {{ history.total }} 条，第 {{ history.page }} / {{ totalPages }} 页
            </p>
            <div class="flex gap-2">
              <button
                @click="changePage(history.page - 1)"
                :disabled="history.page <= 1"
                class="px-3 py-1 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 transition"
              >
                上一页
              </button>
              <button
                @click="changePage(history.page + 1)"
                :disabled="history.page >= totalPages"
                class="px-3 py-1 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 transition"
              >
                下一页
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Line, Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'
import { tokenStatsApi } from '@/api/tokenStats'
import type { TokenStats, AnalysisHistory, DailyTokenStat } from '@/api/tokenStats'

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
)

const loading = ref(true)
const error = ref('')
const mobileMenuOpen = ref(false)

const stats = ref<TokenStats>({
  total_tokens: 0,
  total_paid_tokens: 0,
  average_tokens_per_analysis: 0,
  total_analyses: 0,
  estimated_cost: 0,
  daily_stats: [],
})

const history = ref<AnalysisHistory>({
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
})

// Pie chart time range
type PieRange = '7d' | '30d' | 'all'
const pieRange = ref<PieRange>('30d')
const pieRangeOptions = [
  { value: '7d' as PieRange, label: '7 天' },
  { value: '30d' as PieRange, label: '30 天' },
  { value: 'all' as PieRange, label: '全部' },
]

// Polling
const POLL_INTERVAL = 30000 // 30 seconds
let pollTimer: ReturnType<typeof setInterval> | null = null

const totalPages = computed(() => Math.ceil(history.value.total / history.value.page_size))

// === Line Chart ===
const lineChartData = computed(() => {
  const dailyStats = stats.value.daily_stats
  if (!dailyStats || dailyStats.length === 0) return null

  const labels = dailyStats.map((d) => {
    const date = new Date(d.date)
    return `${date.getMonth() + 1}/${date.getDate()}`
  })

  return {
    labels,
    datasets: [
      {
        label: '每日 Token 消耗',
        data: dailyStats.map((d) => d.total_tokens),
        borderColor: '#7c3aed',
        backgroundColor: 'rgba(124, 58, 237, 0.1)',
        fill: true,
        tension: 0.3,
        pointRadius: 3,
        pointHoverRadius: 5,
      },
    ],
  }
})

const lineChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx: any) => `${ctx.parsed.y.toLocaleString()} tokens`,
      },
    },
  },
  scales: {
    x: {
      grid: { display: false },
      ticks: { font: { size: 11 }, maxRotation: 0 },
    },
    y: {
      beginAtZero: true,
      ticks: {
        font: { size: 11 },
        callback: (value: any) => {
          if (value >= 1000) return (value / 1000).toFixed(0) + 'K'
          return value
        },
      },
    },
  },
}

// === Pie/Doughnut Chart ===
const filteredPieStats = computed(() => {
  const dailyStats = stats.value.daily_stats
  if (!dailyStats || dailyStats.length === 0) return null

  let filtered: DailyTokenStat[]
  if (pieRange.value === 'all') {
    filtered = dailyStats
  } else {
    const days = pieRange.value === '7d' ? 7 : 30
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - days)
    filtered = dailyStats.filter((d) => new Date(d.date) >= cutoff)
  }

  const cacheHit = filtered.reduce((sum, d) => sum + d.cache_hit_tokens, 0)
  const cacheMiss = filtered.reduce((sum, d) => sum + d.cache_miss_tokens, 0)
  const output = filtered.reduce((sum, d) => sum + d.output_tokens, 0)

  return { cacheHit, cacheMiss, output }
})

const pieChartData = computed(() => {
  const data = filteredPieStats.value
  if (!data || (data.cacheHit === 0 && data.cacheMiss === 0 && data.output === 0)) return null

  return {
    labels: ['缓存命中（免费）', '付费输入', '付费输出'],
    datasets: [
      {
        data: [data.cacheHit, data.cacheMiss, data.output],
        backgroundColor: ['#10b981', '#f59e0b', '#6366f1'],
        borderWidth: 2,
        borderColor: '#ffffff',
      },
    ],
  }
})

const pieChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom' as const,
      labels: { font: { size: 12 }, padding: 16 },
    },
    tooltip: {
      callbacks: {
        label: (ctx: any) => {
          const total = ctx.dataset.data.reduce((a: number, b: number) => a + b, 0)
          const pct = total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) : '0'
          return `${ctx.label}: ${ctx.parsed.toLocaleString()} tokens (${pct}%)`
        },
      },
    },
  },
}

// === Data Fetching & Polling ===
onMounted(() => {
  fetchData()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})

function startPolling() {
  stopPolling()
  pollTimer = setInterval(() => {
    refreshData()
  }, POLL_INTERVAL)
}

function stopPolling() {
  if (pollTimer !== null) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function fetchData() {
  loading.value = true
  error.value = ''
  try {
    const [statsData, historyData] = await Promise.all([
      tokenStatsApi.getStats(),
      tokenStatsApi.getHistory({ page: history.value.page, page_size: 20 }),
    ])
    stats.value = statsData
    history.value = historyData
  } catch (err: any) {
    error.value = err.response?.data?.detail || '加载数据失败，请稍后重试'
  }
  loading.value = false
}

/** Silent refresh for polling - does not show loading state */
async function refreshData() {
  try {
    const [statsData, historyData] = await Promise.all([
      tokenStatsApi.getStats(),
      tokenStatsApi.getHistory({ page: history.value.page, page_size: 20 }),
    ])
    stats.value = statsData
    history.value = historyData
  } catch {
    // Silent fail on polling - don't disrupt user experience
  }
}

async function changePage(page: number) {
  if (page < 1 || page > totalPages.value) return
  history.value.page = page
  try {
    const historyData = await tokenStatsApi.getHistory({ page, page_size: 20 })
    history.value = historyData
  } catch (err: any) {
    error.value = err.response?.data?.detail || '加载数据失败'
  }
}

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return String(n)
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function agentModeLabel(mode: string): string {
  const labels: Record<string, string> = {
    chain: 'Chain',
    agent: 'Agent',
    multi_agent: 'Multi-Agent',
  }
  return labels[mode] || mode
}

function agentModeClass(mode: string): string {
  const classes: Record<string, string> = {
    chain: 'bg-gray-100 text-gray-600',
    agent: 'bg-blue-100 text-blue-700',
    multi_agent: 'bg-purple-100 text-purple-700',
  }
  return classes[mode] || 'bg-gray-100 text-gray-600'
}
</script>

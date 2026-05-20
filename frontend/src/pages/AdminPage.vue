<template>
  <div class="min-h-screen py-8 px-6" style="background-color: var(--bg-base);">
    <div class="max-w-6xl mx-auto">
      <!-- 头部 -->
      <div class="flex items-center justify-between mb-8">
        <div class="flex items-center gap-3">
          <span class="text-2xl">🛡️</span>
          <h1 class="text-2xl font-bold font-serif" style="color: var(--text-primary);">管理后台</h1>
        </div>
        <router-link to="/diary" class="text-sm transition" style="color: var(--accent);">← 返回日记</router-link>
      </div>

      <!-- 统计卡片 -->
      <div class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <div class="glass-card rounded-xl p-4 text-center">
          <p class="text-2xl font-bold" style="color: var(--accent);">{{ stats.total_users }}</p>
          <p class="text-xs mt-1" style="color: var(--text-muted);">用户总数</p>
        </div>
        <div class="glass-card rounded-xl p-4 text-center">
          <p class="text-2xl font-bold" style="color: var(--accent);">{{ stats.total_diaries }}</p>
          <p class="text-xs mt-1" style="color: var(--text-muted);">日记总数</p>
        </div>
        <div class="glass-card rounded-xl p-4 text-center">
          <p class="text-2xl font-bold" style="color: var(--accent);">{{ stats.public_diaries }}</p>
          <p class="text-xs mt-1" style="color: var(--text-muted);">公开日记</p>
        </div>
        <div class="glass-card rounded-xl p-4 text-center">
          <p class="text-2xl font-bold" style="color: var(--accent);">{{ stats.total_analyses }}</p>
          <p class="text-xs mt-1" style="color: var(--text-muted);">AI 分析次数</p>
        </div>
        <div class="glass-card rounded-xl p-4 text-center">
          <p class="text-2xl font-bold" style="color: var(--accent);">{{ stats.total_tokens_consumed?.toLocaleString() }}</p>
          <p class="text-xs mt-1" style="color: var(--text-muted);">Token 总消耗</p>
        </div>
      </div>

      <!-- Tab 切换 -->
      <div class="flex gap-1 mb-6 p-1 rounded-xl" style="background: var(--bg-input);">
        <button v-for="tab in tabs" :key="tab.key" @click="activeTab = tab.key"
          class="flex-1 py-2 px-4 rounded-lg text-sm font-medium transition"
          :style="activeTab === tab.key
            ? { background: 'var(--accent-soft)', color: 'var(--accent)' }
            : { color: 'var(--text-muted)' }">
          {{ tab.label }}
        </button>
      </div>

      <!-- ═══ 用户管理 ═══ -->
      <div v-if="activeTab === 'users'" class="glass-card rounded-2xl p-6">
        <div class="flex items-center gap-3 mb-4">
          <input v-model="userSearch" @input="debouncedFetchUsers" placeholder="搜索用户名..." class="input-theme flex-1" style="max-width: 300px;" />
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr style="border-bottom: 1px solid var(--border-base);">
                <th class="th-cell">ID</th>
                <th class="th-cell">用户名</th>
                <th class="th-cell">邮箱</th>
                <th class="th-cell">角色</th>
                <th class="th-cell sortable" @click="toggleSort('users', 'diary_count')">
                  日记数 {{ sortIcon('users', 'diary_count') }}
                </th>
                <th class="th-cell sortable" @click="toggleSort('users', 'age')">
                  年龄 {{ sortIcon('users', 'age') }}
                </th>
                <th class="th-cell sortable" @click="toggleSort('users', 'create_time')">
                  注册时间 {{ sortIcon('users', 'create_time') }}
                </th>
                <th class="th-cell text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.UID" style="border-bottom: 1px solid var(--border-base);">
                <td class="td-cell" style="color: var(--text-faint);">{{ u.UID }}</td>
                <td class="td-cell" style="color: var(--text-primary);">{{ u.user_name }}</td>
                <td class="td-cell" style="color: var(--text-muted);">{{ u.email || '-' }}</td>
                <td class="td-cell">
                  <span class="px-2 py-0.5 rounded-full text-xs"
                    :class="u.role === 'admin' ? 'text-purple-500 bg-purple-500/10' : 'text-green-500 bg-green-500/10'">
                    {{ u.role === 'admin' ? '管理员' : '用户' }}
                  </span>
                </td>
                <td class="td-cell font-medium" style="color: var(--accent);">{{ u.diary_count }}</td>
                <td class="td-cell" style="color: var(--text-muted);">{{ u.age ?? '-' }}</td>
                <td class="td-cell" style="color: var(--text-faint);">{{ formatDate(u.create_time) }}</td>
                <td class="td-cell text-right">
                  <button v-if="u.role !== 'admin'" @click="handleDeleteUser(u.UID)"
                    class="text-xs text-red-400/70 hover:text-red-500 transition">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <Pagination :total="usersTotal" :page="usersPage" @prev="usersPage--; fetchUsers()" @next="usersPage++; fetchUsers()" />
      </div>

      <!-- ═══ 日记管理 ═══ -->
      <div v-if="activeTab === 'diaries'" class="glass-card rounded-2xl p-6">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr style="border-bottom: 1px solid var(--border-base);">
                <th class="th-cell">ID</th>
                <th class="th-cell">用户</th>
                <th class="th-cell">内容摘要</th>
                <th class="th-cell sortable" @click="toggleSort('diaries', 'content_length')">
                  字数 {{ sortIcon('diaries', 'content_length') }}
                </th>
                <th class="th-cell">天气</th>
                <th class="th-cell sortable" @click="toggleSort('diaries', 'create_time')">
                  时间 {{ sortIcon('diaries', 'create_time') }}
                </th>
                <th class="th-cell text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in diaries" :key="d.NID" style="border-bottom: 1px solid var(--border-base);">
                <td class="td-cell" style="color: var(--text-faint);">{{ d.NID }}</td>
                <td class="td-cell" style="color: var(--accent);">{{ d.user_name }}</td>
                <td class="td-cell max-w-xs truncate" style="color: var(--text-primary);">{{ d.content }}</td>
                <td class="td-cell font-medium" style="color: var(--text-muted);">{{ d.content_length }}</td>
                <td class="td-cell" style="color: var(--text-faint);">{{ d.weather || '-' }}</td>
                <td class="td-cell" style="color: var(--text-faint);">{{ formatDate(d.create_time) }}</td>
                <td class="td-cell text-right">
                  <button @click="handleDeleteDiary(d.NID)" class="text-xs text-red-400/70 hover:text-red-500 transition">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <Pagination :total="diariesTotal" :page="diariesPage" @prev="diariesPage--; fetchDiaries()" @next="diariesPage++; fetchDiaries()" />
      </div>

      <!-- ═══ 分析数据 ═══ -->
      <div v-if="activeTab === 'analyses'" class="glass-card rounded-2xl p-6">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr style="border-bottom: 1px solid var(--border-base);">
                <th class="th-cell">ID</th>
                <th class="th-cell">日记ID</th>
                <th class="th-cell sortable" @click="toggleSort('analyses', 'Token_cost')">
                  Token {{ sortIcon('analyses', 'Token_cost') }}
                </th>
                <th class="th-cell sortable" @click="toggleSort('analyses', 'cache_hit_tokens')">
                  缓存命中 {{ sortIcon('analyses', 'cache_hit_tokens') }}
                </th>
                <th class="th-cell sortable" @click="toggleSort('analyses', 'output_tokens')">
                  输出 {{ sortIcon('analyses', 'output_tokens') }}
                </th>
                <th class="th-cell sortable" @click="toggleSort('analyses', 'diary_length')">
                  日记长度 {{ sortIcon('analyses', 'diary_length') }}
                </th>
                <th class="th-cell">模式</th>
                <th class="th-cell sortable" @click="toggleSort('analyses', 'Thk_time')">
                  时间 {{ sortIcon('analyses', 'Thk_time') }}
                </th>
                <th class="th-cell text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in analyses" :key="a.Thk_ID" style="border-bottom: 1px solid var(--border-base);">
                <td class="td-cell" style="color: var(--text-faint);">{{ a.Thk_ID }}</td>
                <td class="td-cell" style="color: var(--text-muted);">{{ a.NID }}</td>
                <td class="td-cell font-medium" style="color: var(--text-primary);">{{ a.Token_cost ?? 0 }}</td>
                <td class="td-cell text-green-500">{{ a.cache_hit_tokens ?? 0 }}</td>
                <td class="td-cell" style="color: var(--accent);">{{ a.output_tokens ?? 0 }}</td>
                <td class="td-cell" style="color: var(--text-muted);">{{ a.diary_length ?? '-' }}</td>
                <td class="td-cell" style="color: var(--text-faint);">{{ a.agent_mode || '-' }}</td>
                <td class="td-cell" style="color: var(--text-faint);">{{ formatDate(a.Thk_time) }}</td>
                <td class="td-cell text-right">
                  <button @click="handleDeleteAnalysis(a.Thk_ID)" class="text-xs text-red-400/70 hover:text-red-500 transition">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <Pagination :total="analysesTotal" :page="analysesPage" @prev="analysesPage--; fetchAnalyses()" @next="analysesPage++; fetchAnalyses()" />
      </div>

      <!-- ═══ 标签审核 ═══ -->
      <div v-if="activeTab === 'tags'" class="glass-card rounded-2xl p-6">
        <h3 class="text-sm font-medium mb-4" style="color: var(--text-secondary);">待审核标签 ({{ pendingTags.length }})</h3>
        <div v-if="!pendingTags.length" class="text-center py-8" style="color: var(--text-faint);">
          暂无待审核标签 ✨
        </div>
        <div v-else class="space-y-3">
          <div v-for="tag in pendingTags" :key="tag.id"
            class="flex items-center justify-between p-4 rounded-xl border" style="border-color: var(--border-base); background: var(--bg-input);">
            <div class="flex items-center gap-3">
              <span class="w-4 h-4 rounded-full" :style="{ backgroundColor: tag.color || '#6B7280' }"></span>
              <span class="font-medium" style="color: var(--text-primary);">#{{ tag.tag_name }}</span>
              <span class="text-xs" style="color: var(--text-faint);">by {{ tag.creator }}</span>
              <span class="text-xs" style="color: var(--text-faint);">{{ formatDate(tag.create_time) }}</span>
            </div>
            <div class="flex items-center gap-2">
              <button @click="handleApproveTag(tag.id)"
                class="px-3 py-1 text-xs font-medium text-green-500 bg-green-500/10 rounded-lg hover:bg-green-500/20 transition">
                通过
              </button>
              <button @click="handleRejectTag(tag.id)"
                class="px-3 py-1 text-xs font-medium text-red-400 bg-red-500/10 rounded-lg hover:bg-red-500/20 transition">
                拒绝
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, h, defineComponent } from 'vue'
import { adminApi } from '@/api/admin'

// 简单分页组件
const Pagination = defineComponent({
  props: { total: { type: Number, default: 0 }, page: { type: Number, default: 0 } },
  emits: ['prev', 'next'],
  setup(props, { emit }) {
    return () => h('div', { class: 'flex justify-between items-center mt-4' }, [
      h('span', { class: 'text-xs', style: 'color: var(--text-faint);' }, `共 ${props.total} 条`),
      h('div', { class: 'flex gap-2' }, [
        h('button', {
          onClick: () => emit('prev'),
          disabled: props.page === 0,
          class: 'px-3 py-1 text-xs rounded-lg border disabled:opacity-30',
          style: 'border-color: var(--border-base); color: var(--text-muted);',
        }, '上一页'),
        h('button', {
          onClick: () => emit('next'),
          disabled: (props.page + 1) * 50 >= props.total,
          class: 'px-3 py-1 text-xs rounded-lg border disabled:opacity-30',
          style: 'border-color: var(--border-base); color: var(--text-muted);',
        }, '下一页'),
      ]),
    ])
  },
})

const tabs = [
  { key: 'users', label: '用户管理' },
  { key: 'diaries', label: '公开日记' },
  { key: 'analyses', label: '分析数据' },
  { key: 'tags', label: '标签审核' },
]
const activeTab = ref('users')

const stats = ref<any>({})

// 排序状态
const sortState = ref<Record<string, { field: string | null; order: 'asc' | 'desc' }>>({
  users: { field: null, order: 'desc' },
  diaries: { field: null, order: 'desc' },
  analyses: { field: null, order: 'desc' },
})

function toggleSort(tab: string, field: string) {
  const s = sortState.value[tab]
  if (s.field === field) {
    s.order = s.order === 'desc' ? 'asc' : 'desc'
  } else {
    s.field = field
    s.order = 'desc'
  }
  // 重新请求
  if (tab === 'users') { usersPage.value = 0; fetchUsers() }
  else if (tab === 'diaries') { diariesPage.value = 0; fetchDiaries() }
  else if (tab === 'analyses') { analysesPage.value = 0; fetchAnalyses() }
}

function sortIcon(tab: string, field: string): string {
  const s = sortState.value[tab]
  if (s.field !== field) return '↕'
  return s.order === 'desc' ? '↓' : '↑'
}

// 用户
const users = ref<any[]>([])
const usersTotal = ref(0)
const usersPage = ref(0)
const userSearch = ref('')

// 日记
const diaries = ref<any[]>([])
const diariesTotal = ref(0)
const diariesPage = ref(0)

// 分析
const analyses = ref<any[]>([])
const analysesTotal = ref(0)
const analysesPage = ref(0)

// 待审核标签
const pendingTags = ref<any[]>([])

let searchTimer: ReturnType<typeof setTimeout> | null = null
function debouncedFetchUsers() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { usersPage.value = 0; fetchUsers() }, 300)
}

onMounted(async () => {
  try { stats.value = await adminApi.getStats() } catch {}
  fetchUsers()
  fetchDiaries()
  fetchAnalyses()
  fetchPendingTags()
})

async function fetchUsers() {
  const s = sortState.value.users
  try {
    const res = await adminApi.listUsers(usersPage.value * 50, 50, userSearch.value || undefined, s.field || undefined, s.order)
    users.value = res.items
    usersTotal.value = res.total
  } catch {}
}

async function fetchDiaries() {
  const s = sortState.value.diaries
  try {
    const res = await adminApi.listDiaries(diariesPage.value * 50, 50, undefined, s.field || undefined, s.order)
    diaries.value = res.items
    diariesTotal.value = res.total
  } catch {}
}

async function fetchAnalyses() {
  const s = sortState.value.analyses
  try {
    const res = await adminApi.listAnalyses(analysesPage.value * 50, 50, undefined, s.field || undefined, s.order)
    analyses.value = res.items
    analysesTotal.value = res.total
  } catch {}
}

async function handleDeleteUser(uid: number) {
  if (!confirm('确定删除该用户？此操作不可撤销。')) return
  try { await adminApi.deleteUser(uid); fetchUsers(); stats.value = await adminApi.getStats() } catch {}
}

async function handleDeleteDiary(nid: number) {
  if (!confirm('确定删除该日记？')) return
  try { await adminApi.deleteDiary(nid); fetchDiaries(); stats.value = await adminApi.getStats() } catch {}
}

async function handleDeleteAnalysis(thkId: number) {
  if (!confirm('确定删除该分析记录？')) return
  try { await adminApi.deleteAnalysis(thkId); fetchAnalyses(); stats.value = await adminApi.getStats() } catch {}
}

async function fetchPendingTags() {
  try { pendingTags.value = await adminApi.listPendingTags() } catch {}
}

async function handleApproveTag(tagId: number) {
  try { await adminApi.approveTag(tagId); fetchPendingTags() } catch {}
}

async function handleRejectTag(tagId: number) {
  if (!confirm('确定拒绝该标签？')) return
  try { await adminApi.rejectTag(tagId); fetchPendingTags() } catch {}
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
.th-cell {
  text-align: left;
  padding: 0.75rem 0.5rem;
  color: var(--text-muted);
  font-weight: 500;
  font-size: 0.75rem;
  white-space: nowrap;
}
.th-cell.sortable {
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}
.th-cell.sortable:hover {
  color: var(--accent);
}
.td-cell {
  padding: 0.75rem 0.5rem;
}
</style>

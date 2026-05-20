<template>
  <div class="min-h-screen relative" style="background-color: var(--bg-base);">
    <!-- 夜间星空背景装饰 -->
    <div class="stars-bg fixed inset-0 pointer-events-none overflow-hidden">
      <div class="absolute top-[5%] right-[10%] w-1.5 h-1.5 bg-star-300/40 rounded-full animate-pulse"></div>
      <div class="absolute top-[12%] left-[20%] w-1 h-1 bg-star-200/30 rounded-full animate-pulse" style="animation-delay: 1s"></div>
      <div class="absolute top-[8%] left-[60%] w-1 h-1 bg-star-300/25 rounded-full animate-pulse" style="animation-delay: 2s"></div>
      <div class="absolute top-[18%] right-[35%] w-1 h-1 bg-white/20 rounded-full animate-pulse" style="animation-delay: 1.5s"></div>
      <div class="absolute top-0 right-0 w-[500px] h-[500px] rounded-full blur-[120px]" style="background: rgba(139,92,246,0.04)"></div>
      <div class="absolute bottom-0 left-0 w-[400px] h-[400px] rounded-full blur-[100px]" style="background: rgba(99,60,200,0.03)"></div>
    </div>

    <!-- 顶部导航 -->
    <nav class="sticky top-0 z-30 border-b" style="background: var(--bg-nav); backdrop-filter: blur(20px); border-color: var(--border-base);">
      <div class="w-full px-6 lg:px-12 py-3.5 flex items-center justify-between">
        <div class="flex items-center gap-3">
          <span class="text-2xl">🌙</span>
          <span class="text-xl font-bold font-serif" style="color: var(--text-primary);">夜记</span>
        </div>
        <div class="flex items-center gap-1">
          <WeatherWidget />
          <router-link to="/tags" class="nav-link">标签</router-link>
          <router-link to="/column" class="nav-link">专栏</router-link>
          <router-link to="/models" class="nav-link">模型</router-link>
          <router-link to="/report" class="nav-link">报表</router-link>
          <router-link to="/token-dashboard" class="nav-link">Token</router-link>
          <router-link to="/help" class="nav-link">帮助</router-link>
          <router-link v-if="user?.role === 'admin'" to="/admin" class="nav-link" style="color: var(--accent);">🛡️ 管理</router-link>
          <button @click="toggleTheme" class="nav-link" :title="currentTheme === 'day' ? '切换夜间模式' : '切换白天模式'">
            {{ currentTheme === 'day' ? '🌙' : '☀️' }}
          </button>
          <router-link to="/profile" class="nav-link font-medium" style="color: var(--accent);">
            {{ user?.user_name || '个人中心' }}
          </router-link>
          <button @click="handleLogout" class="nav-link text-red-400/70 hover:text-red-400">退出</button>
        </div>
      </div>
    </nav>

    <div class="relative w-full px-6 lg:px-12 py-8">
      <div class="grid grid-cols-1 lg:grid-cols-5 gap-8">
        <!-- 左侧 -->
        <div class="lg:col-span-3 space-y-6">
          <DiaryEditor :edit-entry="editingDiary" @created="handleCreated" @editing="handleEditing" @updated="handleUpdated" />
          <DiaryList ref="diaryListRef" @select="selectedEntry = $event" @edit="handleEditDiary" />
        </div>

        <!-- 右侧：AI 分析 -->
        <div class="lg:col-span-2">
          <div class="sticky top-20">
            <div v-if="!selectedEntry" class="glass-card rounded-3xl p-12 text-center">
              <span class="text-5xl block mb-4 animate-float">📖</span>
              <p class="text-lg" style="color: var(--text-muted);">点击左侧日记</p>
              <p class="text-sm mt-1" style="color: var(--text-faint);">查看 AI 总结</p>
            </div>
            <AIAnalysisPanel v-else ref="aiPanelRef" :entry="selectedEntry" @close="selectedEntry = null" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTheme } from '@/composables/useTheme'
import { storeToRefs } from 'pinia'
import DiaryEditor from '@/components/DiaryEditor.vue'
import DiaryList from '@/components/DiaryList.vue'
import AIAnalysisPanel from '@/components/AIAnalysisPanel.vue'
import WeatherWidget from '@/components/WeatherWidget.vue'
import type { DiaryResponse } from '@/types'

const router = useRouter()
const auth = useAuthStore()
const { user } = storeToRefs(auth)
const { currentTheme, toggleTheme } = useTheme()
const diaryListRef = ref<InstanceType<typeof DiaryList> | null>(null)
const selectedEntry = ref<DiaryResponse | null>(null)
const aiPanelRef = ref<InstanceType<typeof AIAnalysisPanel> | null>(null)
const editingDiary = ref<DiaryResponse | null>(null)

function handleEditing() {
  aiPanelRef.value?.notifyEditing()
}

function handleEditDiary(entry: DiaryResponse) {
  editingDiary.value = entry
}

function handleCreated() {
  editingDiary.value = null
  diaryListRef.value?.refresh()
}

function handleUpdated() {
  editingDiary.value = null
  diaryListRef.value?.refresh()
}

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.nav-link {
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  color: var(--text-muted);
  border-radius: 0.5rem;
  transition: all 0.2s;
}
.nav-link:hover {
  color: var(--accent);
  background: var(--accent-soft);
}
</style>

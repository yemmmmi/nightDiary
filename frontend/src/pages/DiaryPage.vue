<template>
  <div class="min-h-screen bg-gradient-to-b from-diary-50/60 to-amber-50/40">
    <!-- 顶部导航 — 大号 -->
    <nav class="sticky top-0 z-30 bg-white/70 backdrop-blur-md border-b border-diary-100">
      <div class="w-full px-12 py-6 flex items-center justify-between">
        <div class="flex items-center gap-4">
          <span class="text-5xl">🌙</span>
          <span class="text-4xl font-bold text-ink-800 font-serif">夜记</span>
        </div>
        <div class="flex items-center gap-8 text-xl">
          <router-link to="/tags" class="text-ink-500 hover:text-diary-600 transition">标签</router-link>
          <router-link to="/models" class="text-ink-500 hover:text-diary-600 transition">模型</router-link>
          <router-link to="/report" class="text-ink-500 hover:text-diary-600 transition">报表</router-link>
          <router-link to="/help" class="text-ink-500 hover:text-diary-600 transition">帮助</router-link>
          <router-link to="/profile" class="text-ink-500 hover:text-diary-600 transition font-medium">
            {{ user?.user_name || '个人中心' }}
          </router-link>
          <button @click="handleLogout" class="text-red-400 hover:text-red-500 transition">退出</button>
        </div>
      </div>
    </nav>

    <div class="w-full px-12 py-12">
      <div class="grid grid-cols-1 lg:grid-cols-5 gap-12">
        <!-- 左侧：编辑器 + 列表 -->
        <div class="lg:col-span-3 space-y-10">
          <DiaryEditor @created="diaryListRef?.refresh()" />
          <DiaryList ref="diaryListRef" @select="selectedEntry = $event" />
        </div>

        <!-- 右侧：AI 分析面板 -->
        <div class="lg:col-span-2">
          <div class="sticky top-32">
            <div v-if="!selectedEntry" class="bg-white/60 backdrop-blur-sm rounded-3xl border border-diary-100 p-16 text-center">
              <span class="text-7xl block mb-5">📖</span>
              <p class="text-ink-400 text-2xl">点击左侧日记</p>
              <p class="text-ink-300 text-xl mt-3">查看 AI 总结</p>
            </div>
            <AIAnalysisPanel v-else :entry="selectedEntry" @close="selectedEntry = null" />
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
import { storeToRefs } from 'pinia'
import DiaryEditor from '@/components/DiaryEditor.vue'
import DiaryList from '@/components/DiaryList.vue'
import AIAnalysisPanel from '@/components/AIAnalysisPanel.vue'
import type { DiaryResponse } from '@/types'

const router = useRouter()
const auth = useAuthStore()
const { user } = storeToRefs(auth)
const diaryListRef = ref<InstanceType<typeof DiaryList> | null>(null)
const selectedEntry = ref<DiaryResponse | null>(null)

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

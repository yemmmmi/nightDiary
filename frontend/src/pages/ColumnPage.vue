<template>
  <div class="min-h-screen bg-gradient-to-b from-diary-50/60 to-amber-50/40">
    <!-- 顶部导航 -->
    <nav class="sticky top-0 z-30 bg-white/70 backdrop-blur-md border-b border-diary-100">
      <div class="w-full px-12 py-6 flex items-center justify-between">
        <div class="flex items-center gap-4">
          <span class="text-5xl">🌙</span>
          <span class="text-4xl font-bold text-ink-800 font-serif">夜记专栏</span>
        </div>
        <div class="flex items-center gap-8 text-xl">
          <router-link
            :to="isAuthenticated ? '/diary' : '/login'"
            class="text-ink-500 hover:text-diary-600 transition"
          >
            {{ isAuthenticated ? '我的日记' : '登录' }}
          </router-link>
        </div>
      </div>
    </nav>

    <div class="w-full px-12 py-12">
      <!-- 加载中 -->
      <div v-if="loading" class="text-center py-20 text-ink-300 text-xl">
        <span class="text-4xl block mb-4">📖</span>加载中...
      </div>

      <!-- 空状态 -->
      <div v-else-if="!entries.length" class="text-center py-24">
        <span class="text-7xl block mb-6">🌙</span>
        <p class="text-ink-400 font-serif text-2xl">暂无公开日记</p>
        <p class="text-ink-300 text-lg mt-3">还没有人发布日记到专栏</p>
      </div>

      <!-- 列表 + 详情 -->
      <template v-else>
        <div class="grid grid-cols-1 lg:grid-cols-5 gap-12">
          <!-- 左侧：卡片列表 -->
          <div class="lg:col-span-3 space-y-6">
            <ColumnDiaryCard
              v-for="entry in entries" :key="entry.NID"
              :entry="entry"
              @click="handleSelect(entry)"
            />

            <div v-if="hasMore" class="text-center py-8">
              <button @click="loadMore" :disabled="loadingMore"
                class="px-8 py-3 text-diary-600 hover:bg-diary-50 rounded-2xl transition text-lg font-medium">
                {{ loadingMore ? '加载中...' : '加载更多' }}
              </button>
            </div>
          </div>

          <!-- 右侧：详情面板 -->
          <div class="lg:col-span-2">
            <div class="sticky top-32">
              <div v-if="!selectedDetail" class="bg-white/60 backdrop-blur-sm rounded-3xl border border-diary-100 p-16 text-center">
                <span class="text-7xl block mb-5">📖</span>
                <p class="text-ink-400 text-2xl">点击左侧日记</p>
                <p class="text-ink-300 text-xl mt-3">查看完整内容</p>
              </div>
              <div v-else-if="loadingDetail" class="bg-white/60 backdrop-blur-sm rounded-3xl border border-diary-100 p-16 text-center">
                <span class="text-4xl block mb-4">📖</span>
                <p class="text-ink-300 text-xl">加载中...</p>
              </div>
              <ColumnDiaryDetail v-else :detail="selectedDetail" @close="selectedDetail = null" />
            </div>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { storeToRefs } from 'pinia'
import { columnApi } from '@/api/column'
import ColumnDiaryCard from '@/components/ColumnDiaryCard.vue'
import ColumnDiaryDetail from '@/components/ColumnDiaryDetail.vue'
import type { PublicDiaryListItem, PublicDiaryDetail } from '@/types'

const auth = useAuthStore()
const { isAuthenticated } = storeToRefs(auth)

const entries = ref<PublicDiaryListItem[]>([])
const loading = ref(true)
const loadingMore = ref(false)
const hasMore = ref(true)
const pageSize = 20

const selectedDetail = ref<PublicDiaryDetail | null>(null)
const loadingDetail = ref(false)

onMounted(() => fetchEntries())

async function fetchEntries() {
  loading.value = true
  try {
    entries.value = await columnApi.list(0, pageSize)
    hasMore.value = entries.value.length >= pageSize
  } catch {}
  loading.value = false
}

async function loadMore() {
  loadingMore.value = true
  try {
    const more = await columnApi.list(entries.value.length, pageSize)
    entries.value.push(...more)
    hasMore.value = more.length >= pageSize
  } catch {}
  loadingMore.value = false
}

async function handleSelect(entry: PublicDiaryListItem) {
  loadingDetail.value = true
  selectedDetail.value = null
  try {
    selectedDetail.value = await columnApi.detail(entry.NID)
  } catch {}
  loadingDetail.value = false
}
</script>

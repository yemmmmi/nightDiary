<template>
  <div class="max-w-3xl mx-auto p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">报表打印</h1>
      <router-link to="/diary" class="text-sm text-blue-600 hover:underline">← 返回日记</router-link>
    </div>

    <div class="space-y-4">
      <!-- 日记列表报表 -->
      <div class="bg-white rounded-xl shadow p-5">
        <h2 class="font-semibold text-gray-800 mb-2">日记列表报表</h2>
        <p class="text-sm text-gray-500 mb-4">导出你的日记列表，包含日期、天气和内容摘要。</p>
        <button
          @click="printDiaryReport"
          :disabled="loadingDiary"
          class="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition text-sm"
        >
          {{ loadingDiary ? '生成中...' : '打印日记报表' }}
        </button>
      </div>

      <!-- 个人信息报表 -->
      <div class="bg-white rounded-xl shadow p-5">
        <h2 class="font-semibold text-gray-800 mb-2">个人信息报表</h2>
        <p class="text-sm text-gray-500 mb-4">导出你的个人信息和日记统计数据。</p>
        <button
          @click="printProfileReport"
          :disabled="!user"
          class="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition text-sm"
        >
          打印个人报表
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { storeToRefs } from 'pinia'
import { diaryApi } from '@/api/diary'
import type { DiaryResponse } from '@/types'

const auth = useAuthStore()
const { user } = storeToRefs(auth)
const loadingDiary = ref(false)

function openPrintWindow(html: string) {
  const win = window.open('', '_blank')
  if (!win) return
  win.document.write(html)
  win.document.close()
  win.onload = () => { win.print() }
}

async function printDiaryReport() {
  loadingDiary.value = true
  try {
    const entries: DiaryResponse[] = await diaryApi.list(0, 100)
    const rows = entries.map(e => {
      const date = e.create_time ? new Date(e.create_time).toLocaleDateString('zh-CN') : '-'
      const weather = e.weather || '-'
      const snippet = (e.content || '').slice(0, 80) + ((e.content || '').length > 80 ? '...' : '')
      return `<tr><td>${date}</td><td>${weather}</td><td>${snippet}</td></tr>`
    }).join('')

    openPrintWindow(`<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
      <title>日记报表</title>
      <style>body{font-family:sans-serif;padding:20px}table{width:100%;border-collapse:collapse}
      th,td{border:1px solid #ddd;padding:8px;text-align:left;font-size:13px}
      th{background:#f5f5f5}h1{font-size:20px;margin-bottom:16px}</style></head>
      <body><h1>日记报表 — ${user.value?.user_name || ''}</h1>
      <p>共 ${entries.length} 篇日记</p>
      <table><thead><tr><th>日期</th><th>天气</th><th>内容摘要</th></tr></thead>
      <tbody>${rows}</tbody></table></body></html>`)
  } catch { /* ignore */ }
  loadingDiary.value = false
}

function printProfileReport() {
  if (!user.value) return
  const u = user.value
  openPrintWindow(`<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
    <title>个人信息报表</title>
    <style>body{font-family:sans-serif;padding:20px}table{border-collapse:collapse;margin-top:12px}
    td{padding:6px 16px;font-size:14px}td:first-child{font-weight:bold;color:#555}
    h1{font-size:20px;margin-bottom:16px}</style></head>
    <body><h1>个人信息报表</h1>
    <table>
      <tr><td>用户名</td><td>${u.user_name}</td></tr>
      <tr><td>邮箱</td><td>${u.email || '-'}</td></tr>
      <tr><td>性别</td><td>${u.gender === 'M' ? '男' : u.gender === 'F' ? '女' : u.gender || '-'}</td></tr>
      <tr><td>年龄</td><td>${u.age ?? '-'}</td></tr>
      <tr><td>电话</td><td>${u.phone || '-'}</td></tr>
      <tr><td>地址</td><td>${u.address || '-'}</td></tr>
      <tr><td>角色</td><td>${u.role || '-'}</td></tr>
      <tr><td>注册时间</td><td>${u.create_time ? new Date(u.create_time).toLocaleDateString('zh-CN') : '-'}</td></tr>
    </table></body></html>`)
}
</script>

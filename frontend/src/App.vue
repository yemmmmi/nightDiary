<template>
  <div class="min-h-screen" style="background-color: var(--bg-base); transition: background-color 0.6s ease;">
    <RouterView />
  </div>
</template>

<script setup lang="ts">
import { useTheme } from '@/composables/useTheme'

// 初始化日夜主题（根据当前时间自动判断）
useTheme()
</script>

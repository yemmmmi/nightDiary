<template>
  <transition name="weather-fade">
    <div v-if="weatherInfo" :class="['weather-widget', themeClass]">
      <div class="weather-bg" />
      <div class="relative z-10 flex items-center gap-3 px-5 py-3">
        <span class="text-2xl">{{ icon }}</span>
        <div class="flex flex-col leading-tight">
          <span class="text-sm font-semibold" :class="textClass">{{ mainText }}</span>
          <span class="text-xs opacity-75" :class="textClass">{{ detailText }}</span>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { storeToRefs } from 'pinia'

const auth = useAuthStore()
const { weatherInfo } = storeToRefs(auth)

// 解析天气字符串，格式如 "晴 28°C 湿度 45% 南风 3级"
const parsed = computed(() => {
  if (!weatherInfo.value) return null
  const raw = weatherInfo.value
  const weatherMatch = raw.match(/^(\S+)\s/)
  const tempMatch = raw.match(/(-?\d+)°C/)
  const humidityMatch = raw.match(/湿度\s*(\d+)%/)
  const windMatch = raw.match(/([\u4e00-\u9fa5]+风\s*\d+级)/)
  return {
    weather: weatherMatch?.[1] || raw,
    temp: tempMatch?.[1] || null,
    humidity: humidityMatch?.[1] || null,
    wind: windMatch?.[1] || null,
  }
})

type WeatherTheme = 'sunny' | 'cloudy' | 'rainy' | 'thunderstorm' | 'snowy'

const theme = computed<WeatherTheme>(() => {
  const w = parsed.value?.weather || ''
  if (/雷/.test(w)) return 'thunderstorm'
  if (/雨|阵雨/.test(w)) return 'rainy'
  if (/雪|冰/.test(w)) return 'snowy'
  if (/阴|多云|云/.test(w)) return 'cloudy'
  return 'sunny'
})

const icon = computed(() => {
  const map: Record<WeatherTheme, string> = {
    sunny: '☀️',
    cloudy: '⛅',
    rainy: '🌧️',
    thunderstorm: '⛈️',
    snowy: '❄️',
  }
  return map[theme.value]
})

const themeClass = computed(() => `theme-${theme.value}`)

const textClass = computed(() => {
  const map: Record<WeatherTheme, string> = {
    sunny: 'text-amber-900',
    cloudy: 'text-slate-700',
    rainy: 'text-blue-900',
    thunderstorm: 'text-purple-100',
    snowy: 'text-sky-900',
  }
  return map[theme.value]
})

const mainText = computed(() => {
  if (!parsed.value) return ''
  const { weather, temp } = parsed.value
  return temp ? `${weather} ${temp}°C` : weather
})

const detailText = computed(() => {
  if (!parsed.value) return ''
  const parts: string[] = []
  if (parsed.value.humidity) parts.push(`湿度 ${parsed.value.humidity}%`)
  if (parsed.value.wind) parts.push(parsed.value.wind)
  return parts.join(' · ') || ''
})
</script>

<style scoped>
.weather-widget {
  position: relative;
  border-radius: 1rem;
  overflow: hidden;
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.3);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  transition: all 0.4s ease;
  min-width: 180px;
}

.weather-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  transition: background 0.6s ease;
}

/* 晴天 — 暖金渐变 */
.theme-sunny .weather-bg {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 50%, #fbbf24 100%);
  opacity: 0.7;
}
.theme-sunny {
  border-color: rgba(251, 191, 36, 0.3);
}

/* 多云 — 灰蓝渐变 */
.theme-cloudy .weather-bg {
  background: linear-gradient(135deg, #f1f5f9 0%, #cbd5e1 50%, #94a3b8 100%);
  opacity: 0.7;
}
.theme-cloudy {
  border-color: rgba(148, 163, 184, 0.3);
}

/* 雨天 — 蓝灰渐变 */
.theme-rainy .weather-bg {
  background: linear-gradient(135deg, #dbeafe 0%, #93c5fd 50%, #60a5fa 100%);
  opacity: 0.65;
}
.theme-rainy {
  border-color: rgba(96, 165, 250, 0.3);
}

/* 雷雨 — 深紫暗蓝渐变 */
.theme-thunderstorm .weather-bg {
  background: linear-gradient(135deg, #1e1b4b 0%, #4c1d95 40%, #6d28d9 70%, #312e81 100%);
  opacity: 0.85;
}
.theme-thunderstorm {
  border-color: rgba(139, 92, 246, 0.4);
  box-shadow: 0 2px 16px rgba(109, 40, 217, 0.2);
}

/* 雪天 — 冰蓝渐变 */
.theme-snowy .weather-bg {
  background: linear-gradient(135deg, #f0f9ff 0%, #bae6fd 50%, #7dd3fc 100%);
  opacity: 0.7;
}
.theme-snowy {
  border-color: rgba(125, 211, 252, 0.3);
}

/* 进入/离开动画 */
.weather-fade-enter-active {
  transition: all 0.5s ease;
}
.weather-fade-leave-active {
  transition: all 0.3s ease;
}
.weather-fade-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}
.weather-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>

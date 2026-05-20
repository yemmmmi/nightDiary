<template>
  <transition name="weather-fade">
    <div v-if="weatherInfo" class="weather-widget" :class="themeClass">
      <div class="weather-bg" />
      <div class="relative z-10 flex items-center gap-2 px-3.5 py-2">
        <span class="text-base">{{ icon }}</span>
        <div class="flex flex-col leading-tight">
          <span class="text-xs font-semibold" style="color: var(--text-primary);">{{ mainText }}</span>
          <span class="text-[10px]" style="color: var(--text-muted);">{{ detailText }}</span>
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

const parsed = computed(() => {
  if (!weatherInfo.value) return null
  const raw = weatherInfo.value
  const weatherMatch = raw.match(/^(\S+)\s/)
  const tempMatch = raw.match(/(-?\d+)°C/)
  const humidityMatch = raw.match(/湿度\s*(\d+)%/)
  const windMatch = raw.match(/([\u4e00-\u9fa5]+风\s*\d+级)/)
  return { weather: weatherMatch?.[1] || raw, temp: tempMatch?.[1] || null, humidity: humidityMatch?.[1] || null, wind: windMatch?.[1] || null }
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

const icon = computed(() => ({ sunny: '☀️', cloudy: '⛅', rainy: '🌧️', thunderstorm: '⛈️', snowy: '❄️' })[theme.value])
const themeClass = computed(() => `theme-${theme.value}`)
const mainText = computed(() => parsed.value ? (parsed.value.temp ? `${parsed.value.weather} ${parsed.value.temp}°C` : parsed.value.weather) : '')
const detailText = computed(() => {
  if (!parsed.value) return ''
  const parts: string[] = []
  if (parsed.value.humidity) parts.push(`湿度 ${parsed.value.humidity}%`)
  if (parsed.value.wind) parts.push(parsed.value.wind)
  return parts.join(' · ')
})
</script>

<style scoped>
.weather-widget {
  position: relative;
  border-radius: 0.75rem;
  overflow: hidden;
  border: 1px solid var(--border-base);
  transition: all 0.4s ease;
  min-width: 140px;
}
.weather-bg {
  position: absolute; inset: 0; z-index: 0;
  background: var(--bg-input);
  transition: background 0.6s ease;
}
.theme-sunny .weather-bg { background: rgba(251, 191, 36, 0.08); }
.theme-sunny { border-color: rgba(251, 191, 36, 0.2); }
.theme-cloudy .weather-bg { background: rgba(148, 163, 184, 0.06); }
.theme-rainy .weather-bg { background: rgba(96, 165, 250, 0.06); }
.theme-rainy { border-color: rgba(96, 165, 250, 0.15); }
.theme-thunderstorm .weather-bg { background: rgba(139, 92, 246, 0.08); }
.theme-thunderstorm { border-color: rgba(139, 92, 246, 0.2); }
.theme-snowy .weather-bg { background: rgba(125, 211, 252, 0.06); }

.weather-fade-enter-active { transition: all 0.5s ease; }
.weather-fade-leave-active { transition: all 0.3s ease; }
.weather-fade-enter-from, .weather-fade-leave-to { opacity: 0; transform: translateY(-6px); }
</style>

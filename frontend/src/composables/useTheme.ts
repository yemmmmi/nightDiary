/**
 * 日夜主题切换 Composable
 * 
 * 根据当前时间自动切换：
 * - 白天 (6:00 - 18:00)：温暖明亮的奶油色调
 * - 夜晚 (18:00 - 6:00)：深靛紫星空色调
 * 
 * 通过在 <html> 元素上添加 data-theme="day" | "night" 实现
 */
import { ref, onMounted, onUnmounted } from 'vue'

export type Theme = 'day' | 'night'

const currentTheme = ref<Theme>('day')

function getThemeByTime(): Theme {
  const hour = new Date().getHours()
  return (hour >= 6 && hour < 18) ? 'day' : 'night'
}

function applyTheme(theme: Theme) {
  document.documentElement.setAttribute('data-theme', theme)
  currentTheme.value = theme
}

let timer: ReturnType<typeof setInterval> | null = null

export function useTheme() {
  onMounted(() => {
    applyTheme(getThemeByTime())
    // 每分钟检查一次是否需要切换
    timer = setInterval(() => {
      const newTheme = getThemeByTime()
      if (newTheme !== currentTheme.value) {
        applyTheme(newTheme)
      }
    }, 60000)
  })

  onUnmounted(() => {
    if (timer) clearInterval(timer)
  })

  function toggleTheme() {
    applyTheme(currentTheme.value === 'day' ? 'night' : 'day')
  }

  return { currentTheme, toggleTheme }
}

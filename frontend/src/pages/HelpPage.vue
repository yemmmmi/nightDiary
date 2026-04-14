<template>
  <div class="max-w-3xl mx-auto p-6">
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">帮助中心</h1>
      <router-link to="/diary" class="text-sm text-blue-600 hover:underline">← 返回日记</router-link>
    </div>

    <!-- Tab 切换 -->
    <div class="flex gap-1 bg-gray-100 rounded-lg p-1 mb-6">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        @click="activeTab = tab.key"
        :class="[
          'flex-1 py-2 rounded-md text-sm font-medium transition',
          activeTab === tab.key ? 'bg-white shadow text-blue-600' : 'text-gray-500 hover:text-gray-700'
        ]"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 新手引导 -->
    <div v-if="activeTab === 'guide'" class="space-y-4">
      <div
        v-for="(step, i) in guideSteps"
        :key="i"
        class="bg-white rounded-xl shadow p-5 flex gap-4"
      >
        <div class="w-8 h-8 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center font-bold text-sm shrink-0">
          {{ i + 1 }}
        </div>
        <div>
          <h3 class="font-semibold text-gray-800 mb-1">{{ step.title }}</h3>
          <p class="text-sm text-gray-600">{{ step.desc }}</p>
        </div>
      </div>
    </div>

    <!-- FAQ -->
    <div v-if="activeTab === 'faq'" class="space-y-3">
      <div class="mb-4">
        <input
          v-model="faqSearch"
          type="text"
          placeholder="搜索常见问题..."
          class="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
        />
      </div>
      <div
        v-for="(item, i) in filteredFaq"
        :key="i"
        class="bg-white rounded-xl shadow overflow-hidden"
      >
        <button
          @click="toggleFaq(i)"
          class="w-full px-5 py-4 text-left flex items-center justify-between hover:bg-gray-50 transition"
        >
          <span class="font-medium text-gray-800 text-sm">{{ item.q }}</span>
          <span class="text-gray-400 text-xs">{{ openFaq.has(i) ? '收起' : '展开' }}</span>
        </button>
        <div v-if="openFaq.has(i)" class="px-5 pb-4 text-sm text-gray-600 leading-relaxed">
          {{ item.a }}
        </div>
      </div>
      <p v-if="!filteredFaq.length" class="text-center py-8 text-gray-400 text-sm">未找到匹配的问题</p>
    </div>

    <!-- 反馈留言 -->
    <div v-if="activeTab === 'feedback'" class="bg-white rounded-xl shadow p-5">
      <form @submit.prevent="handleFeedback">
        <textarea
          v-model="feedback"
          rows="5"
          placeholder="请描述你遇到的问题或建议..."
          class="w-full px-4 py-3 border border-gray-300 rounded-lg resize-none focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
        />
        <div class="mt-3 flex items-center justify-between">
          <span class="text-sm text-gray-400">{{ feedback.length }} / 500</span>
          <button
            type="submit"
            :disabled="!feedback.trim() || feedbackSent"
            class="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-40 transition text-sm"
          >
            {{ feedbackSent ? '已提交，感谢反馈' : '提交反馈' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

const tabs = [
  { key: 'guide', label: '新手引导' },
  { key: 'faq', label: '常见问题' },
  { key: 'feedback', label: '反馈留言' },
]
const activeTab = ref('guide')

// 新手引导步骤
const guideSteps = [
  { title: '注册账号', desc: '点击右上角「注册」，输入用户名和密码即可创建账号。邮箱为选填项。' },
  { title: '写日记', desc: '登录后进入日记页面，在顶部编辑器中写下今天的内容，可以选择标签分类。点击「发布日记」保存。' },
  { title: '获取 AI 分析', desc: '点击日记列表中的任意一篇日记，右侧会出现 AI 分析面板。点击「获取 AI 分析」，夜记助手会给你温暖的回应。' },
  { title: '管理标签', desc: '进入「标签」页面，可以创建自定义标签并选择颜色。写日记时可以选择标签来分类。' },
  { title: '配置 AI 模型', desc: '进入「模型」页面，可以注册自己的 LLM 模型（如 DeepSeek、OpenAI）。系统会优先使用你配置的模型进行分析。' },
  { title: '导出报表', desc: '进入「报表」页面，可以将日记列表或个人信息导出为可打印的 HTML 格式。' },
]

// FAQ
const faqData = [
  { q: 'AI 分析需要多长时间？', a: '通常 5-15 秒，取决于日记长度和 LLM 服务的响应速度。如果超过 30 秒，可能是 AI 服务暂时不可用。' },
  { q: '我的日记数据安全吗？', a: '你的日记数据存储在服务器数据库中，通过 JWT 认证保护。每个用户只能访问自己的数据，其他用户无法查看。' },
  { q: '如何更换 AI 模型？', a: '进入「模型管理」页面，注册新模型并确保其状态为「活跃」。系统会自动使用你配置的活跃模型。' },
  { q: '标签有什么用？', a: '标签帮助你分类日记（如「工作」「生活」「学习」），AI 分析时会参考标签来更好地理解日记内容。' },
  { q: '日记内容未变化时为什么不能重新分析？', a: '这是智能防重机制，避免在内容没有变化时重复消耗 AI Token。修改日记内容后即可重新分析。' },
  { q: '忘记密码怎么办？', a: '当前版本暂不支持密码找回功能，请联系管理员重置密码。' },
  { q: '如何注销账号？', a: '进入「个人中心」页面，点击底部的「注销账号」按钮。注意：此操作不可撤销，所有数据将被永久删除。' },
  { q: '支持哪些 LLM 模型？', a: '支持所有兼容 OpenAI API 格式的模型，包括 DeepSeek、通义千问、OpenAI GPT 系列、LM Studio 本地模型等。' },
]
const faqSearch = ref('')
const openFaq = ref(new Set<number>())

const filteredFaq = computed(() => {
  if (!faqSearch.value.trim()) return faqData
  const kw = faqSearch.value.toLowerCase()
  return faqData.filter(item => item.q.toLowerCase().includes(kw) || item.a.toLowerCase().includes(kw))
})

function toggleFaq(i: number) {
  if (openFaq.value.has(i)) openFaq.value.delete(i)
  else openFaq.value.add(i)
}

// 反馈
const feedback = ref('')
const feedbackSent = ref(false)

function handleFeedback() {
  if (!feedback.value.trim()) return
  // MVP: 前端提示已提交，后续可接入后端 API
  feedbackSent.value = true
}
</script>

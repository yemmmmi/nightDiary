/**
 * Bug 条件探索性测试 — 记住我登录功能
 *
 * 验证修复后代码中 token 存储的正确行为：
 * - setToken() 根据 rememberMe 参数选择存储位置
 * - rememberMe=false 时 token 存入 sessionStorage
 * - clearAuth() 同时清除 localStorage 和 sessionStorage
 *
 * **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useAuthStore } from '@/stores/auth'

// Mock authApi
vi.mock('@/api/auth', () => ({
  authApi: {
    login: vi.fn().mockResolvedValue({ access_token: 'test-token', token_type: 'bearer' }),
    me: vi.fn().mockResolvedValue({
      UID: 1, user_name: 'testuser', email: null, phone: null,
      age: null, gender: null, address: null, role: null, create_time: null,
    }),
    logout: vi.fn().mockResolvedValue(undefined),
    register: vi.fn().mockResolvedValue({
      UID: 1, user_name: 'testuser', email: null, phone: null,
      age: null, gender: null, address: null, role: null, create_time: null,
    }),
  },
}))

describe('Bug 条件探索性测试 — Token 存储行为', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    setActivePinia(createPinia())
  })

  it('修复后 — 默认登录 token 不在 localStorage 中', async () => {
    const store = useAuthStore()
    await store.login('testuser', 'password123')

    // 修复后：默认 rememberMe=false，token 不应在 localStorage 中
    expect(localStorage.getItem('token')).toBeNull()
  })

  it('修复后 — 默认登录 token 在 sessionStorage 中', async () => {
    const store = useAuthStore()
    await store.login('testuser', 'password123')

    // 修复后：默认 rememberMe=false，token 应在 sessionStorage 中
    expect(sessionStorage.getItem('token')).toBe('test-token')
  })

  it('修复后 — clearAuth 清除 sessionStorage 中的 token', async () => {
    // 手动在 sessionStorage 中设置 token（模拟修复后的场景）
    sessionStorage.setItem('token', 'session-test-token')

    const store = useAuthStore()
    // 先登录以设置状态
    await store.login('testuser', 'password123')
    // 登出（内部调用 clearAuth）
    await store.logout()

    // 修复后：clearAuth 同时清除 localStorage 和 sessionStorage
    expect(sessionStorage.getItem('token')).toBeNull()
  })

  it('期望行为 — rememberMe=false 时 token 应在 sessionStorage 而非 localStorage', async () => {
    /**
     * 此测试编码了期望的修复后行为：
     * 当 rememberMe=false 时，token 应存入 sessionStorage，不应在 localStorage 中。
     *
     * 在未修复代码上，此测试应该 FAIL，因为：
     * 1. login() 不接受 rememberMe 参数
     * 2. setToken() 总是存入 localStorage
     *
     * **Validates: Requirements 2.1, 2.7**
     */
    const store = useAuthStore()

    // 调用 login 并传入 rememberMe=false
    // 在未修复代码中，login 签名是 login(username, password)，第三个参数被忽略
    await store.login('testuser', 'password123', false as any)

    // 期望行为：token 应在 sessionStorage 中
    expect(sessionStorage.getItem('token')).toBe('test-token')
    // 期望行为：token 不应在 localStorage 中
    expect(localStorage.getItem('token')).toBeNull()
  })
})

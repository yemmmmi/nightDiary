/**
 * 保持性属性测试 — 记住我登录功能
 *
 * 这些测试捕获当前（未修复）代码中的正确行为，
 * 确保修复后这些行为不会被破坏（无回归）。
 *
 * 所有测试在未修复代码上应该 PASS。
 *
 * **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
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

describe('保持性属性测试 — 登录/登出行为不变', () => {
  beforeEach(() => {
    localStorage.clear()
    sessionStorage.clear()
    setActivePinia(createPinia())
  })

  it('登录成功后 isAuthenticated 为 true', async () => {
    const store = useAuthStore()
    await store.login('testuser', 'password123')

    expect(store.isAuthenticated).toBe(true)
  })

  it('登录成功后 token 不为空', async () => {
    const store = useAuthStore()
    await store.login('testuser', 'password123')

    expect(store.token).toBe('test-token')
  })

  it('登出后 token 为 null', async () => {
    const store = useAuthStore()
    await store.login('testuser', 'password123')
    await store.logout()

    expect(store.token).toBeNull()
  })

  it('登出后 isAuthenticated 为 false', async () => {
    const store = useAuthStore()
    await store.login('testuser', 'password123')
    await store.logout()

    expect(store.isAuthenticated).toBe(false)
  })

  it('登出后 user 为 null', async () => {
    const store = useAuthStore()
    await store.login('testuser', 'password123')
    await store.logout()

    expect(store.user).toBeNull()
  })

  it('登出后 localStorage 中无 token', async () => {
    const store = useAuthStore()
    await store.login('testuser', 'password123')
    await store.logout()

    expect(localStorage.getItem('token')).toBeNull()
  })

  it('rememberMe=true 时 token 存入 localStorage', async () => {
    /**
     * 保持性属性：当前代码中 login 不接受 rememberMe 参数，
     * token 总是存入 localStorage。修复后，当 rememberMe=true 时
     * token 仍应存入 localStorage，行为与原始代码一致。
     *
     * 在未修复代码上：login 忽略第三个参数，token 存入 localStorage → PASS
     * 在修复后代码上：login 接受 rememberMe=true，token 存入 localStorage → PASS
     */
    const store = useAuthStore()
    await store.login('testuser', 'password123', true)

    expect(localStorage.getItem('token')).toBe('test-token')
  })
})

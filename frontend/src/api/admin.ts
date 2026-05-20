import http from './http'

export const adminApi = {
  getStats: async () => {
    const res = await http.get('/admin/stats')
    return res.data
  },

  listUsers: async (skip = 0, limit = 50, search?: string, sortBy?: string, sortOrder?: string) => {
    const params: Record<string, any> = { skip, limit }
    if (search) params.search = search
    if (sortBy) params.sort_by = sortBy
    if (sortOrder) params.sort_order = sortOrder
    const res = await http.get('/admin/users', { params })
    return res.data
  },

  deleteUser: async (uid: number) => {
    await http.delete(`/admin/users/${uid}`)
  },

  updateUserRole: async (uid: number, role: string) => {
    const res = await http.put(`/admin/users/${uid}/role`, null, { params: { role } })
    return res.data
  },

  listDiaries: async (skip = 0, limit = 50, userId?: number, sortBy?: string, sortOrder?: string) => {
    const params: Record<string, any> = { skip, limit }
    if (userId) params.user_id = userId
    if (sortBy) params.sort_by = sortBy
    if (sortOrder) params.sort_order = sortOrder
    const res = await http.get('/admin/diaries', { params })
    return res.data
  },

  getDiary: async (nid: number) => {
    const res = await http.get(`/admin/diaries/${nid}`)
    return res.data
  },

  deleteDiary: async (nid: number) => {
    await http.delete(`/admin/diaries/${nid}`)
  },

  listAnalyses: async (skip = 0, limit = 50, userId?: number, sortBy?: string, sortOrder?: string) => {
    const params: Record<string, any> = { skip, limit }
    if (userId) params.user_id = userId
    if (sortBy) params.sort_by = sortBy
    if (sortOrder) params.sort_order = sortOrder
    const res = await http.get('/admin/analyses', { params })
    return res.data
  },

  deleteAnalysis: async (thkId: number) => {
    await http.delete(`/admin/analyses/${thkId}`)
  },

  // 标签审核
  listPendingTags: async () => {
    const res = await http.get('/admin/tags/pending')
    return res.data
  },

  approveTag: async (tagId: number) => {
    const res = await http.put(`/admin/tags/${tagId}/approve`)
    return res.data
  },

  rejectTag: async (tagId: number) => {
    await http.delete(`/admin/tags/${tagId}/reject`)
  },
}

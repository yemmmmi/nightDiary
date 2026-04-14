import http from './http'
import type { TagResponse } from '@/types'

export const tagsApi = {
  list: async (): Promise<TagResponse[]> => {
    const res = await http.get('/tags/')
    return res.data
  },

  create: async (tag_name: string, color?: string): Promise<TagResponse> => {
    const res = await http.post('/tags/', { tag_name, color })
    return res.data
  },

  update: async (tagId: number, data: { tag_name?: string; color?: string }): Promise<TagResponse> => {
    const res = await http.put(`/tags/${tagId}`, data)
    return res.data
  },

  delete: async (tagId: number): Promise<void> => {
    await http.delete(`/tags/${tagId}`)
  },
}

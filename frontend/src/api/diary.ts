import http from './http'
import type { DiaryResponse } from '@/types'

export interface DiaryCreatePayload {
  content: string
  mood?: string
  is_public?: boolean
  tag_ids?: number[]
}

export interface DiaryUpdatePayload {
  content?: string
  is_open?: boolean
  tag_ids?: number[]
}

export const diaryApi = {
  create: async (data: DiaryCreatePayload): Promise<DiaryResponse> => {
    const res = await http.post('/diary/entries', data)
    return res.data
  },

  list: async (skip = 0, limit = 20): Promise<DiaryResponse[]> => {
    const res = await http.get('/diary/entries', { params: { skip, limit } })
    return res.data
  },

  get: async (entryId: number): Promise<DiaryResponse> => {
    const res = await http.get(`/diary/entries/${entryId}`)
    return res.data
  },

  update: async (entryId: number, data: DiaryUpdatePayload): Promise<DiaryResponse> => {
    const res = await http.put(`/diary/entries/${entryId}`, data)
    return res.data
  },

  delete: async (entryId: number): Promise<void> => {
    await http.delete(`/diary/entries/${entryId}`)
  },
}

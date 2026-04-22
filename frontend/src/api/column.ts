import http from './http'
import type { PublicDiaryListItem, PublicDiaryDetail } from '@/types'

export const columnApi = {
  list: async (skip = 0, limit = 20): Promise<PublicDiaryListItem[]> => {
    const res = await http.get('/public/column/entries', { params: { skip, limit } })
    return res.data
  },

  detail: async (nid: number): Promise<PublicDiaryDetail> => {
    const res = await http.get(`/public/column/entries/${nid}`)
    return res.data
  },

  publish: async (nid: number): Promise<{ message: string; nid: number }> => {
    const res = await http.post(`/public/column/entries/${nid}/publish`)
    return res.data
  },

  unpublish: async (nid: number): Promise<{ message: string; nid: number }> => {
    const res = await http.delete(`/public/column/entries/${nid}/publish`)
    return res.data
  },
}

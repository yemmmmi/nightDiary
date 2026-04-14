import http from './http'
import type { AnalysisResponse } from '@/types'

export const analysisApi = {
  create: async (nid: number): Promise<AnalysisResponse> => {
    const res = await http.post('/analysis', { nid })
    return res.data
  },

  get: async (nid: number): Promise<AnalysisResponse> => {
    const res = await http.get(`/analysis/${nid}`)
    return res.data
  },

  update: async (nid: number): Promise<AnalysisResponse> => {
    const res = await http.put(`/analysis/${nid}`)
    return res.data
  },

  delete: async (thkId: number): Promise<void> => {
    await http.delete(`/analysis/${thkId}`)
  },
}

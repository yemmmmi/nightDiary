import http from './http'
import type { ModelResponse } from '@/types'

export interface ModelCreatePayload {
  model_name?: string
  model_key: string
  base_url: string
}

export interface ModelUpdatePayload {
  model_name?: string
  model_key?: string
  base_url?: string
}

export const modelsApi = {
  list: async (): Promise<ModelResponse[]> => {
    const res = await http.get('/models/')
    return res.data
  },

  create: async (data: ModelCreatePayload): Promise<ModelResponse> => {
    const res = await http.post('/models/', data)
    return res.data
  },

  update: async (modelId: number, data: ModelUpdatePayload): Promise<ModelResponse> => {
    const res = await http.put(`/models/${modelId}`, data)
    return res.data
  },

  delete: async (modelId: number): Promise<void> => {
    await http.delete(`/models/${modelId}`)
  },
}

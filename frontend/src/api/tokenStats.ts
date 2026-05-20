import http from './http'

// === Types ===

export interface DailyTokenStat {
  date: string
  total_tokens: number
  cache_hit_tokens: number
  cache_miss_tokens: number
  output_tokens: number
}

export interface TokenStats {
  total_tokens: number
  total_paid_tokens: number
  average_tokens_per_analysis: number
  total_analyses: number
  estimated_cost: number
  daily_stats: DailyTokenStat[]
}

export interface AnalysisHistoryItem {
  thk_id: number
  diary_nid: number
  date: string | null
  diary_snippet: string
  total_tokens: number | null
  cache_hit_tokens: number | null
  cache_miss_tokens: number | null
  output_tokens: number | null
  agent_mode: string | null
  activated_agents: string | null
}

export interface AnalysisHistory {
  items: AnalysisHistoryItem[]
  total: number
  page: number
  page_size: number
}

// === API ===

export interface StatsParams {
  start_date?: string
  end_date?: string
  granularity?: 'daily' | 'weekly' | 'monthly'
}

export interface HistoryParams {
  page?: number
  page_size?: number
}

export const tokenStatsApi = {
  /** 获取聚合 Token 统计 */
  getStats: async (params?: StatsParams): Promise<TokenStats> => {
    const res = await http.get('/analysis/stats', { params })
    return res.data
  },

  /** 获取分页分析历史 */
  getHistory: async (params?: HistoryParams): Promise<AnalysisHistory> => {
    const res = await http.get('/analysis/history', { params })
    return res.data
  },
}

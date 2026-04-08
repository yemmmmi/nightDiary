// 用户
export interface UserResponse {
  uid: number
  user_name: string
  email: string
  role: string
  create_time: string
  last_time: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

// 标签
export interface TagResponse {
  tid: number
  tag_name: string
  color: string | null
  creator: string
  usage_cnt: number
}

// 日记
export interface DiaryResponse {
  nid: number
  uid: number
  content: string
  is_open: boolean
  date: string
  weather: string | null
  ai_ans: string | null
  tags: TagResponse[]
  create_time: string
}

// 分析
export interface AnalysisResponse {
  thk_id: number
  nid: number
  thk_time: string
  token_cost: number | null
  thk_log: string | null
  diary_length: number | null
}

// 模型
export interface ModelResponse {
  mod_id: number
  model_name: string
  base_url: string
  is_active: boolean
  create_time: string
}

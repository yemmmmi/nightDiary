// 用户
export interface UserResponse {
  UID: number
  user_name: string
  email: string | null
  phone: string | null
  age: number | null
  gender: string | null
  address: string | null
  role: string | null
  create_time: string | null
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

// 标签
export interface TagResponse {
  id: number
  tag_name: string | null
  color: string | null
  creator: string | null
  usage_count: number
  create_time: string | null
}

// 日记
export interface DiaryResponse {
  NID: number
  UID: number | null
  content: string | null
  is_open: boolean
  date: string | null
  weather: string | null
  AI_ans: string | null
  create_time: string | null
  tags: TagResponse[]
}

// 分析
export interface AnalysisResponse {
  Thk_ID: number
  NID: number
  Thk_time: string | null
  Token_cost: number | null
  cache_hit_tokens: number | null
  cache_miss_tokens: number | null
  output_tokens: number | null
  Thk_log: string | null
  diary_length: number | null
}

// 模型
export interface ModelResponse {
  id: number
  model_name: string
  base_url: string | null
  is_active: boolean
  create_time: string | null
}

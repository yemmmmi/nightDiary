import http from './http'

export interface ExplicitFeedbackRequest {
  diary_nid: number
  response_style: string
  feedback_type: 'positive' | 'negative'
  reason?: string | null
}

export interface ImplicitFeedbackRequest {
  diary_nid: number
  response_style: string
  signal_type: 'read_complete' | 'inspired_writing' | 'frequent_usage'
}

export interface FeedbackAck {
  success: boolean
  message: string
}

export const feedbackApi = {
  /** 提交显式反馈（点赞/点踩） */
  submitExplicit: async (data: ExplicitFeedbackRequest): Promise<FeedbackAck> => {
    const res = await http.post('/feedback', data)
    return res.data
  },

  /** 提交隐式反馈信号 */
  submitImplicit: async (data: ImplicitFeedbackRequest): Promise<FeedbackAck> => {
    const res = await http.post('/feedback/implicit', data)
    return res.data
  },
}

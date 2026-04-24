import api from './index';

export interface RecommendationItem {
  id: number;
  title: string;
  authors?: string;
  similarity?: number | null;
  match_reason?: string;
  reason?: string;
  score?: number;
  abstract_preview?: string;
  page_count?: number;
  reading_status?: string;
  category?: string;
  created_at?: string;
}

export interface ComprehensiveRecommendationResponse {
  total: number;
  source_paper_id?: number | null;
  recommendations: RecommendationItem[];
}

export interface FeedbackPayload {
  paper_id: number;
  feedback_type: 'useful' | 'not_useful';
  source?: string;
  comment?: string;
}

export const recommendationApi = {
  /** 综合推荐（内容相似 + 个性化 + 知识图谱） */
  getComprehensive: (params: { paper_id?: number; top_k?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.paper_id != null) query.append('paper_id', String(params.paper_id));
    if (params.top_k != null) query.append('top_k', String(params.top_k));
    const qs = query.toString();
    return api.get<ComprehensiveRecommendationResponse>(
      `/recommendations/comprehensive${qs ? '?' + qs : ''}`
    );
  },

  /** 内容相似推荐（基于指定论文） */
  getSimilar: (paperId: number, topK = 5) =>
    api.get(`/papers/${paperId}/recommendations?top_k=${topK}`),

  /** 个性化推荐 */
  getPersonalized: (topK = 5) =>
    api.get(`/recommendations?top_k=${topK}`),

  /** 刷新论文推荐缓存 */
  refreshCache: (paperId: number) =>
    api.post(`/papers/${paperId}/recommendations/refresh`),

  /** 网络学术推荐 */
  getWebRecommendations: (paperId: number, maxResults = 8) =>
    api.get(`/papers/${paperId}/web-recommendations?max_results=${maxResults}`),

  /** 提交推荐反馈 */
  submitFeedback: (payload: FeedbackPayload) =>
    api.post('/recommendations/feedback', payload),
};

export default recommendationApi;

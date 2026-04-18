import api from './index';
import { AxiosPromise } from 'axios';

interface KnowledgeCardListParams {
  page?: number;
  page_size?: number;
  search?: string;
  category?: string;
  source_type?: string;
  tag?: string;
}

export const knowledgeApi = {
  // 获取知识卡片列表
  getCards: (params: KnowledgeCardListParams = {}): AxiosPromise => {
    const { page = 1, page_size = 20, search, category, source_type, tag } = params;
    const queryParams = new URLSearchParams();
    queryParams.append('page', String(page));
    queryParams.append('page_size', String(page_size));
    if (search) queryParams.append('search', search);
    if (category) queryParams.append('category', category);
    if (source_type) queryParams.append('source_type', source_type);
    if (tag) queryParams.append('tag', tag);
    return api.get(`/knowledge/cards?${queryParams.toString()}`);
  },

  // 获取单张卡片详情
  getCard: (cardId: number | string): AxiosPromise => api.get(`/knowledge/cards/${cardId}`),

  // 创建知识卡片
  createCard: (data: Record<string, any>): AxiosPromise => api.post('/knowledge/cards', data),

  // 更新知识卡片
  updateCard: (cardId: number | string, data: Record<string, any>): AxiosPromise => api.put(`/knowledge/cards/${cardId}`, data),

  // 删除知识卡片
  deleteCard: (cardId: number | string): AxiosPromise => api.delete(`/knowledge/cards/${cardId}`),

  // 从高亮创建知识卡片
  createFromHighlight: (highlightId: number | string): AxiosPromise => api.post(`/knowledge/cards/from-highlight/${highlightId}`),

  // 从问答创建知识卡片
  createFromChat: (content: string, paperId: number | null = null): AxiosPromise => api.post('/knowledge/cards/from-chat', {
    content,
    paper_id: paperId
  }),

  // 搜索知识卡片
  searchCards: (query: string, topK: number = 10): AxiosPromise => api.get(`/knowledge/search?query=${encodeURIComponent(query)}&top_k=${topK}`),

  // 获取知识图谱数据
  getGraphData: (): AxiosPromise => api.get('/knowledge/graph'),

  // 获取统计信息
  getStats: (): AxiosPromise => api.get('/knowledge/stats'),

  // 自动发现关联
  findRelations: (cardId: number | string): AxiosPromise => api.post(`/knowledge/cards/${cardId}/find-relations`),

  // 获取卡片关联
  getCardRelations: (cardId: number | string): AxiosPromise => api.get(`/knowledge/cards/${cardId}/relations`),

  // 创建关联
  createRelation: (sourceCardId: number | string, targetCardId: number | string, relationType: string, description: string = '', confidence: number = 0.8): AxiosPromise => 
    api.post(`/knowledge/relations?source_card_id=${sourceCardId}`, {
      target_card_id: targetCardId,
      relation_type: relationType,
      description,
      confidence
    }),

  // 删除关联
  deleteRelation: (relationId: number | string): AxiosPromise => api.delete(`/knowledge/relations/${relationId}`),

  // 自动生成标签
  autoTag: (cardId: number | string): AxiosPromise => api.post(`/knowledge/cards/${cardId}/auto-tag`),
};

export default knowledgeApi;

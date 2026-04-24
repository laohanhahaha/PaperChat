import api from './index';

/**
 * 知识图谱 API（D3 力导向图专用）
 * 后端端点前缀：/api/v1/knowledge-graph
 */
export const knowledgeGraphApi = {
  /** 获取用户全量知识图谱 */
  getGraph: (userId: number | string) => api.get(`/knowledge-graph/${userId}`),

  /** 按论文筛选子图 */
  getGraphByPaper: (userId: number | string, paperId: number | string) =>
    api.get(`/knowledge-graph/${userId}/paper/${paperId}`),

  /** 构建某篇论文的知识图谱 */
  buildGraph: (paperId: number | string, userId: number | string) =>
    api.post(`/knowledge-graph/build/${paperId}?user_id=${userId}`),

  /** 搜索图谱节点 */
  searchGraph: (userId: number | string, query: string) =>
    api.get(`/knowledge-graph/${userId}/search?query=${encodeURIComponent(query)}`),
};

export default knowledgeGraphApi;

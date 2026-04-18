import api from './index';
import { AxiosPromise } from 'axios';

interface PaperListParams {
  page?: number;
  page_size?: number;
  search?: string;
  category?: string;
  reading_status?: string;
}

export const paperApi = {
  // 论文列表
  getPapers: (params: PaperListParams = {}): AxiosPromise => {
    const { page = 1, page_size = 20, search, category, reading_status } = params;
    const queryParams = new URLSearchParams();
    queryParams.append('page', String(page));
    queryParams.append('page_size', String(page_size));
    if (search) queryParams.append('search', search);
    if (category) queryParams.append('category', category);
    if (reading_status) queryParams.append('reading_status', reading_status);
    return api.get(`/papers?${queryParams.toString()}`);
  },

  // 单篇论文详情
  getPaper: (id: number | string): AxiosPromise => api.get(`/papers/${id}`),

  // 上传论文
  uploadPaper: (file: File, metadata: Record<string, any> = {}, onProgress?: (percent: number) => void): AxiosPromise => {
    const formData = new FormData();
    formData.append('file', file);
    if (metadata.title) formData.append('title', metadata.title);
    if (metadata.category) formData.append('category', metadata.category);
    if (metadata.tags) formData.append('tags', metadata.tags);
    
    return api.post('/papers/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress ? (progressEvent: any) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(percentCompleted);
      } : undefined,
    });
  },

  // 删除论文
  deletePaper: (id: number | string): AxiosPromise => api.delete(`/papers/${id}`),

  // 更新论文
  updatePaper: (id: number | string, data: Record<string, any>): AxiosPromise => api.put(`/papers/${id}`, data),

  // 获取论文文件 URL
  getPaperFileUrl: (id: number | string): string => `/api/v1/papers/${id}/file`,

  // 获取论文全文文本
  getPaperText: (id: number | string): AxiosPromise => api.get(`/papers/${id}/text`),

  // 标记阅读状态
  markAsReading: (paperId: number | string): AxiosPromise => api.patch(`/papers/${paperId}/reading-status`, { status: 'reading' }),

  // 获取相似论文推荐
  getRecommendations: (paperId: number | string, topK: number = 5): AxiosPromise => api.get(`/papers/${paperId}/recommendations?top_k=${topK}`),

  // 获取个性化推荐
  getPersonalRecommendations: (topK: number = 5): AxiosPromise => api.get(`/recommendations?top_k=${topK}`),

  // 获取网络学术推荐
  getWebRecommendations: (paperId: number | string, maxResults: number = 8): AxiosPromise => api.get(`/papers/${paperId}/web-recommendations`, {
    params: { max_results: maxResults }
  }),

  // 手动提取关键词
  extractKeywords: (paperId: number | string): AxiosPromise => api.post(`/papers/${paperId}/extract-keywords`),

  // 批量上传多个 PDF 文件
  batchUpload: (files: File[], onProgress?: (percent: number) => void): AxiosPromise => {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    return api.post('/papers/batch-upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress ? (progressEvent: any) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(percentCompleted);
      } : undefined,
    });
  },

  // 批量上传 ZIP 文件
  batchUploadZip: (zipFile: File, onProgress?: (percent: number) => void): AxiosPromise => {
    const formData = new FormData();
    formData.append('file', zipFile);
    return api.post('/papers/batch-upload-zip', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress ? (progressEvent: any) => {
        const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(percentCompleted);
      } : undefined,
    });
  },
};

export default paperApi;

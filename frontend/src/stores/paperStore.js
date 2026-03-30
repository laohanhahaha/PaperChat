import { create } from 'zustand';
import api from '../api';

const usePaperStore = create((set, get) => ({
  papers: [],
  total: 0,
  loading: false,
  error: null,
  currentPaper: null,
  
  // 推荐相关状态
  recommendations: [],
  personalRecommendations: [],
  recommendationsLoading: false,
  personalRecommendationsLoading: false,
  
  // 网络学术推荐状态
  webRecommendations: [],
  webRecommendationsLoading: false,
  
  // 获取论文列表
  fetchPapers: async (params = {}) => {
    set({ loading: true, error: null });
    try {
      const { page = 1, page_size = 20, search, category, reading_status } = params;
      const queryParams = new URLSearchParams();
      queryParams.append('page', page);
      queryParams.append('page_size', page_size);
      if (search) queryParams.append('search', search);
      if (category) queryParams.append('category', category);
      if (reading_status) queryParams.append('reading_status', reading_status);
      
      const response = await api.get(`/papers?${queryParams.toString()}`);
      set({ 
        papers: response.data.papers, 
        total: response.data.total,
        loading: false 
      });
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '获取论文列表失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 获取单篇论文详情
  fetchPaper: async (id) => {
    set({ loading: true, error: null });
    try {
      const response = await api.get(`/papers/${id}`);
      set({ currentPaper: response.data, loading: false });
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '获取论文详情失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 上传论文
  uploadPaper: async (file, metadata = {}) => {
    set({ loading: true, error: null });
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (metadata.title) formData.append('title', metadata.title);
      if (metadata.category) formData.append('category', metadata.category);
      if (metadata.tags) formData.append('tags', metadata.tags);
      
      const response = await api.post('/papers/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          // 可以在这里添加进度回调
          console.log('上传进度:', percentCompleted);
        },
      });
      
      // 更新列表
      const { papers } = get();
      set({ 
        papers: [response.data, ...papers],
        total: get().total + 1,
        loading: false 
      });
      
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '上传论文失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 删除论文
  deletePaper: async (id) => {
    set({ loading: true, error: null });
    try {
      await api.delete(`/papers/${id}`);
      
      // 更新列表
      const { papers } = get();
      set({ 
        papers: papers.filter(p => p.id !== id),
        total: get().total - 1,
        loading: false 
      });
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '删除论文失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 更新论文
  updatePaper: async (id, data) => {
    set({ loading: true, error: null });
    try {
      const response = await api.put(`/papers/${id}`, data);
      
      // 更新列表中的论文
      const { papers } = get();
      const updatedPapers = papers.map(p => 
        p.id === id ? response.data : p
      );
      
      set({ 
        papers: updatedPapers,
        currentPaper: response.data,
        loading: false 
      });
      
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '更新论文失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 获取论文文件 URL
  getPaperFileUrl: (id) => {
    return `/api/papers/${id}/file`;
  },
  
  // 获取论文全文文本
  fetchPaperText: async (id) => {
    try {
      const response = await api.get(`/papers/${id}/text`);
      return response.data;
    } catch (error) {
      throw error;
    }
  },
  
  // 清除错误
  clearError: () => set({ error: null }),
  
  // 清除当前论文
  clearCurrentPaper: () => set({ currentPaper: null }),
  
  // 标记论文阅读状态并更新阅读时间
  markAsReading: async (paperId) => {
    try {
      const response = await api.patch(`/papers/${paperId}/reading-status`, { status: 'reading' });
      // 更新当前论文信息
      const { currentPaper, papers } = get();
      if (currentPaper && currentPaper.id === paperId) {
        set({
          currentPaper: {
            ...currentPaper,
            reading_status: response.data.reading_status,
            last_read_at: response.data.last_read_at
          }
        });
      }
      // 更新列表中的论文
      const updatedPapers = papers.map(p =>
        p.id === paperId
          ? { ...p, reading_status: response.data.reading_status, last_read_at: response.data.last_read_at }
          : p
      );
      set({ papers: updatedPapers });
      return response.data;
    } catch (error) {
      console.error('标记阅读状态失败:', error);
      throw error;
    }
  },
  
  // 获取相似论文推荐
  fetchRecommendations: async (paperId, topK = 5) => {
    set({ recommendationsLoading: true, error: null });
    try {
      const response = await api.get(`/papers/${paperId}/recommendations?top_k=${topK}`);
      set({ 
        recommendations: response.data.recommendations,
        recommendationsLoading: false 
      });
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '获取推荐失败',
        recommendationsLoading: false 
      });
      throw error;
    }
  },
  
  // 获取个性化推荐
  fetchPersonalRecommendations: async (topK = 5) => {
    set({ personalRecommendationsLoading: true, error: null });
    try {
      const response = await api.get(`/recommendations?top_k=${topK}`);
      set({ 
        personalRecommendations: response.data.recommendations,
        personalRecommendationsLoading: false 
      });
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '获取个性化推荐失败',
        personalRecommendationsLoading: false 
      });
      throw error;
    }
  },
  
  // 清除推荐数据
  clearRecommendations: () => set({ recommendations: [], personalRecommendations: [] }),
  
  // 获取网络学术推荐
  fetchWebRecommendations: async (paperId, maxResults = 8) => {
    set({ webRecommendationsLoading: true });
    try {
      const response = await api.get(`/papers/${paperId}/web-recommendations`, {
        params: { max_results: maxResults }
      });
      set({ 
        webRecommendations: response.data.results,
        webRecommendationsLoading: false 
      });
      return response.data;
    } catch (error) {
      console.error('网络推荐搜索失败:', error);
      set({ webRecommendationsLoading: false });
      throw error;
    }
  },
  
  // 清除网络推荐数据
  clearWebRecommendations: () => set({ webRecommendations: [] }),
  
  // 手动提取关键词
  extractKeywords: async (paperId) => {
    try {
      const res = await api.post(`/papers/${paperId}/extract-keywords`);
      // 更新 store 中的论文数据
      set(state => ({
        papers: state.papers.map(p => 
          p.id === paperId ? { ...p, tags: JSON.stringify(res.data.keywords) } : p
        )
      }));
      return res.data.keywords;
    } catch (err) {
      console.warn('提取关键词失败:', err);
      return [];
    }
  },
  
  // 批量上传多个 PDF 文件
  batchUpload: async (files, onProgress) => {
    set({ loading: true, error: null });
    try {
      const formData = new FormData();
      files.forEach(file => formData.append('files', file));
      
      const response = await api.post('/papers/batch-upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          if (onProgress) onProgress(percentCompleted);
        },
      });
      
      // 刷新论文列表
      const { fetchPapers } = get();
      await fetchPapers({ page: 1, page_size: 20 });
      
      set({ loading: false });
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '批量上传失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 批量上传 ZIP 文件
  batchUploadZip: async (zipFile, onProgress) => {
    set({ loading: true, error: null });
    try {
      const formData = new FormData();
      formData.append('file', zipFile);
      
      const response = await api.post('/papers/batch-upload-zip', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          if (onProgress) onProgress(percentCompleted);
        },
      });
      
      // 刷新论文列表
      const { fetchPapers } = get();
      await fetchPapers({ page: 1, page_size: 20 });
      
      set({ loading: false });
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || 'ZIP 导入失败', 
        loading: false 
      });
      throw error;
    }
  },
  
}));

export default usePaperStore;

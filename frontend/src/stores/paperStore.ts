import { create } from 'zustand';
import { paperApi } from '../api/paperApi';

interface Paper {
  id: number | string;
  title?: string;
  reading_status?: string;
  last_read_at?: string;
  tags?: string;
  [key: string]: any;
}

interface CachedPaper {
  data: Paper;
  timestamp: number;
}

interface PaperState {
  papers: Paper[];
  total: number;
  loading: boolean;
  error: string | null;
  currentPaper: Paper | null;
  paperCache: Record<string, CachedPaper>;
  recommendations: any[];
  personalRecommendations: any[];
  recommendationsLoading: boolean;
  personalRecommendationsLoading: boolean;
  webRecommendations: any[];
  webRecommendationsLoading: boolean;

  fetchPapers: (params?: Record<string, any>) => Promise<any>;
  fetchPaper: (id: number | string) => Promise<any>;
  invalidatePaperCache: (id: number | string) => void;
  clearPaperCache: () => void;
  uploadPaper: (file: File, metadata?: Record<string, any>, onProgress?: (percent: number) => void) => Promise<any>;
  deletePaper: (id: number | string) => Promise<void>;
  updatePaper: (id: number | string, data: Record<string, any>) => Promise<any>;
  getPaperFileUrl: (id: number | string) => string;
  fetchPaperText: (id: number | string) => Promise<any>;
  clearError: () => void;
  clearCurrentPaper: () => void;
  markAsReading: (paperId: number | string) => Promise<any>;
  fetchRecommendations: (paperId: number | string, topK?: number) => Promise<any>;
  fetchPersonalRecommendations: (topK?: number) => Promise<any>;
  clearRecommendations: () => void;
  fetchWebRecommendations: (paperId: number | string, maxResults?: number) => Promise<any>;
  clearWebRecommendations: () => void;
  extractKeywords: (paperId: number | string) => Promise<any>;
  batchUpload: (files: File[], onProgress?: (percent: number) => void) => Promise<any>;
  batchUploadZip: (zipFile: File, onProgress?: (percent: number) => void) => Promise<any>;
}

const CACHE_TTL = 5 * 60 * 1000; // 5 分钟缓存过期时间

const usePaperStore = create<PaperState>((set, get) => ({
  papers: [],
  total: 0,
  loading: false,
  error: null,
  currentPaper: null,
  
  // 论文缓存: { [id]: { data, timestamp } }
  paperCache: {},
  
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
      const response = await paperApi.getPapers(params);
      set({ 
        papers: response.data.papers, 
        total: response.data.total,
        loading: false 
      });
      return response.data;
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || '获取论文列表失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 获取单篇论文详情（带缓存）
  fetchPaper: async (id) => {
    const cached = get().paperCache[id];
    if (cached && (Date.now() - cached.timestamp < CACHE_TTL)) {
      set({ currentPaper: cached.data, loading: false });
      return cached.data;
    }
    
    set({ loading: true, error: null });
    try {
      const response = await paperApi.getPaper(id);
      set(state => ({
        currentPaper: response.data,
        paperCache: { 
          ...state.paperCache, 
          [id]: { data: response.data, timestamp: Date.now() } 
        },
        loading: false 
      }));
      return response.data;
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || '获取论文详情失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 清除指定论文缓存
  invalidatePaperCache: (id) => {
    set(state => {
      const newCache = { ...state.paperCache };
      delete newCache[String(id)];
      return { paperCache: newCache };
    });
  },
  
  // 清除所有论文缓存
  clearPaperCache: () => {
    set({ paperCache: {} });
  },
  
  // 上传论文
  uploadPaper: async (file, metadata = {}, onProgress) => {
    set({ loading: true, error: null });
    try {
      const response = await paperApi.uploadPaper(file, metadata, onProgress);
      
      // 更新列表
      const { papers } = get();
      set({ 
        papers: [response.data, ...papers],
        total: get().total + 1,
        loading: false 
      });
      
      return response.data;
    } catch (error: any) {
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
      await paperApi.deletePaper(id);
      
      // 更新列表并清除缓存
      const { papers } = get();
      set(state => {
        const newCache = { ...state.paperCache };
        delete newCache[String(id)];
        return { 
          papers: papers.filter(p => p.id !== id),
          total: get().total - 1,
          paperCache: newCache,
          loading: false 
        };
      });
    } catch (error: any) {
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
      const response = await paperApi.updatePaper(id, data);
      
      // 更新列表中的论文
      const { papers } = get();
      const updatedPapers = papers.map(p => 
        p.id === id ? response.data : p
      );
      
      // 更新缓存
      set(state => ({
        papers: updatedPapers,
        currentPaper: response.data,
        paperCache: {
          ...state.paperCache,
          [id]: { data: response.data, timestamp: Date.now() }
        },
        loading: false 
      }));
      
      return response.data;
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || '更新论文失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 获取论文文件 URL
  getPaperFileUrl: (id) => paperApi.getPaperFileUrl(id),
  
  // 获取论文全文文本
  fetchPaperText: async (id) => {
    const response = await paperApi.getPaperText(id);
    return response.data;
  },
  
  // 清除错误
  clearError: () => set({ error: null }),
  
  // 清除当前论文
  clearCurrentPaper: () => set({ currentPaper: null }),
  
  // 标记论文阅读状态并更新阅读时间
  markAsReading: async (paperId) => {
    try {
      const response = await paperApi.markAsReading(paperId);
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
    } catch (error: any) {
      console.error('标记阅读状态失败:', error);
      throw error;
    }
  },
  
  // 获取相似论文推荐
  fetchRecommendations: async (paperId, topK = 5) => {
    set({ recommendationsLoading: true, error: null });
    try {
      const response = await paperApi.getRecommendations(paperId, topK);
      set({ 
        recommendations: response.data.recommendations,
        recommendationsLoading: false 
      });
      return response.data;
    } catch (error: any) {
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
      const response = await paperApi.getPersonalRecommendations(topK);
      set({ 
        personalRecommendations: response.data.recommendations,
        personalRecommendationsLoading: false 
      });
      return response.data;
    } catch (error: any) {
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
      const response = await paperApi.getWebRecommendations(paperId, maxResults);
      set({ 
        webRecommendations: response.data.results,
        webRecommendationsLoading: false 
      });
      return response.data;
    } catch (error: any) {
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
      const res = await paperApi.extractKeywords(paperId);
      // 更新 store 中的论文数据
      set(state => ({
        papers: state.papers.map(p => 
          p.id === paperId ? { ...p, tags: JSON.stringify(res.data.keywords) } : p
        )
      }));
      return res.data.keywords;
    } catch (err: any) {
      console.warn('提取关键词失败:', err);
      return [];
    }
  },
  
  // 批量上传多个 PDF 文件
  batchUpload: async (files, onProgress) => {
    set({ loading: true, error: null });
    try {
      const response = await paperApi.batchUpload(files, onProgress);
      
      // 刷新论文列表
      const { fetchPapers } = get();
      await fetchPapers({ page: 1, page_size: 20 });
      
      set({ loading: false });
      return response.data;
    } catch (error: any) {
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
      const response = await paperApi.batchUploadZip(zipFile, onProgress);
      
      // 刷新论文列表
      const { fetchPapers } = get();
      await fetchPapers({ page: 1, page_size: 20 });
      
      set({ loading: false });
      return response.data;
    } catch (error: any) {
      set({ 
        error: error.response?.data?.detail || 'ZIP 导入失败', 
        loading: false 
      });
      throw error;
    }
  },
  
}));

export default usePaperStore;

import { create } from 'zustand';
import api from '../api';

const useHighlightStore = create((set) => ({
  highlights: [],        // 当前论文的所有高亮
  activeHighlight: null, // 当前选中的高亮
  loading: false,
  error: null,
  
  // 加载论文的所有高亮
  fetchHighlights: async (paperId) => {
    set({ loading: true, error: null });
    try {
      const response = await api.get(`/highlights/paper/${paperId}`);
      set({ highlights: response.data, loading: false });
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '获取高亮标注失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 创建高亮
  createHighlight: async (data) => {
    set({ loading: true, error: null });
    try {
      const response = await api.post('/highlights', data);
      const newHighlight = response.data;
      set(state => ({ 
        highlights: [...state.highlights, newHighlight],
        loading: false 
      }));
      return newHighlight;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '创建高亮标注失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 更新高亮
  updateHighlight: async (id, data) => {
    set({ loading: true, error: null });
    try {
      const response = await api.put(`/highlights/${id}`, data);
      const updatedHighlight = response.data;
      set(state => ({
        highlights: state.highlights.map(h => 
          h.id === id ? updatedHighlight : h
        ),
        loading: false
      }));
      return updatedHighlight;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '更新高亮标注失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 删除高亮
  deleteHighlight: async (id) => {
    set({ loading: true, error: null });
    try {
      await api.delete(`/highlights/${id}`);
      set(state => ({
        highlights: state.highlights.filter(h => h.id !== id),
        activeHighlight: state.activeHighlight?.id === id ? null : state.activeHighlight,
        loading: false
      }));
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '删除高亮标注失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 设置当前选中高亮
  setActiveHighlight: (highlight) => {
    set({ activeHighlight: highlight });
  },
  
  // 清空
  clearHighlights: () => {
    set({ highlights: [], activeHighlight: null, error: null });
  },
  
  // 清除错误
  clearError: () => set({ error: null }),
}));

export default useHighlightStore;

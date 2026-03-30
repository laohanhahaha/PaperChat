import { create } from 'zustand';
import api from '../api';

const useNoteStore = create((set, get) => ({
  notes: [],             // 当前论文的所有笔记
  activeNote: null,      // 当前选中的笔记
  searchResults: [],     // 搜索结果
  loading: false,
  error: null,
  
  // 加载论文的所有笔记
  fetchNotes: async (paperId) => {
    set({ loading: true, error: null });
    try {
      const response = await api.get('/notes', { params: { paper_id: paperId } });
      set({ notes: response.data, loading: false });
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '获取笔记失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 创建笔记
  createNote: async (data) => {
    set({ loading: true, error: null });
    try {
      const response = await api.post('/notes', data);
      const newNote = response.data;
      set(state => ({ 
        notes: [newNote, ...state.notes],
        loading: false 
      }));
      return newNote;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '创建笔记失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 更新笔记
  updateNote: async (id, data) => {
    set({ loading: true, error: null });
    try {
      const response = await api.put(`/notes/${id}`, data);
      const updatedNote = response.data;
      set(state => ({
        notes: state.notes.map(n => 
          n.id === id ? { ...n, ...updatedNote } : n
        ),
        activeNote: state.activeNote?.id === id ? { ...state.activeNote, ...updatedNote } : state.activeNote,
        loading: false
      }));
      return updatedNote;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '更新笔记失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 删除笔记
  deleteNote: async (id) => {
    set({ loading: true, error: null });
    try {
      await api.delete(`/notes/${id}`);
      set(state => ({
        notes: state.notes.filter(n => n.id !== id),
        activeNote: state.activeNote?.id === id ? null : state.activeNote,
        loading: false
      }));
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '删除笔记失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 搜索笔记
  searchNotes: async (query, paperId = null) => {
    set({ loading: true, error: null });
    try {
      const params = { q: query };
      if (paperId) {
        params.paper_id = paperId;
      }
      const response = await api.get('/notes/search', { params });
      set({ searchResults: response.data, loading: false });
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '搜索笔记失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 获取单个笔记详情
  fetchNote: async (id) => {
    set({ loading: true, error: null });
    try {
      const response = await api.get(`/notes/${id}`);
      set({ activeNote: response.data, loading: false });
      return response.data;
    } catch (error) {
      set({ 
        error: error.response?.data?.detail || '获取笔记详情失败', 
        loading: false 
      });
      throw error;
    }
  },
  
  // 设置当前选中笔记
  setActiveNote: (note) => {
    set({ activeNote: note });
  },
  
  // 清空搜索结果
  clearSearchResults: () => {
    set({ searchResults: [] });
  },
  
  // 清空笔记
  clearNotes: () => {
    set({ notes: [], activeNote: null, searchResults: [], error: null });
  },
  
  // 清除错误
  clearError: () => set({ error: null }),
}));

export default useNoteStore;

import { create } from 'zustand';
import api from '../api';

const useKnowledgeStore = create((set, get) => ({
    // 状态
    cards: [],
    totalCount: 0,
    currentCard: null,
    searchResults: [],
    graphData: null,
    stats: null,
    loading: false,
    error: null,
    
    // 分页和筛选状态
    currentPage: 1,
    pageSize: 20,
    filters: {
        category: null,
        sourceType: null,
        tag: null,
        search: ''
    },
    
    // 设置加载状态
    setLoading: (loading) => set({ loading }),
    
    // 清除错误
    clearError: () => set({ error: null }),
    
    // 设置筛选条件
    setFilters: (filters) => set({ filters: { ...get().filters, ...filters }, currentPage: 1 }),
    
    // 清除筛选
    clearFilters: () => set({ 
        filters: { category: null, sourceType: null, tag: null, search: '' },
        currentPage: 1 
    }),
    
    // 获取知识卡片列表
    fetchCards: async (params = {}) => {
        const { currentPage, pageSize, filters } = get();
        
        set({ loading: true, error: null });
        
        try {
            const queryParams = new URLSearchParams();
            queryParams.append('page', params.page || currentPage);
            queryParams.append('page_size', params.pageSize || pageSize);
            
            if (filters.search) queryParams.append('search', filters.search);
            if (filters.category) queryParams.append('category', filters.category);
            if (filters.sourceType) queryParams.append('source_type', filters.sourceType);
            if (filters.tag) queryParams.append('tag', filters.tag);
            
            const response = await api.get(`/knowledge/cards?${queryParams.toString()}`);
            
            set({
                cards: response.data.cards,
                totalCount: response.data.total,
                currentPage: response.data.page,
                pageSize: response.data.page_size,
                loading: false
            });
            
            return response.data;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '获取知识卡片失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 获取单张卡片详情
    fetchCard: async (cardId) => {
        set({ loading: true, error: null });
        
        try {
            const response = await api.get(`/knowledge/cards/${cardId}`);
            set({ currentCard: response.data, loading: false });
            return response.data;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '获取卡片详情失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 创建知识卡片
    createCard: async (data) => {
        set({ loading: true, error: null });
        
        try {
            const response = await api.post('/knowledge/cards', data);
            
            // 更新列表
            const { cards, totalCount } = get();
            set({
                cards: [response.data, ...cards],
                totalCount: totalCount + 1,
                loading: false
            });
            
            return response.data;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '创建知识卡片失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 更新知识卡片
    updateCard: async (cardId, data) => {
        set({ loading: true, error: null });
        
        try {
            const response = await api.put(`/knowledge/cards/${cardId}`, data);
            
            // 更新列表中的卡片
            const { cards, currentCard } = get();
            const updatedCards = cards.map(c => 
                c.id === cardId ? response.data : c
            );
            
            set({
                cards: updatedCards,
                currentCard: currentCard?.id === cardId ? response.data : currentCard,
                loading: false
            });
            
            return response.data;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '更新知识卡片失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 删除知识卡片
    deleteCard: async (cardId) => {
        set({ loading: true, error: null });
        
        try {
            await api.delete(`/knowledge/cards/${cardId}`);
            
            // 从列表中移除
            const { cards, totalCount, currentCard } = get();
            set({
                cards: cards.filter(c => c.id !== cardId),
                totalCount: totalCount - 1,
                currentCard: currentCard?.id === cardId ? null : currentCard,
                loading: false
            });
            
            return true;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '删除知识卡片失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 从高亮创建知识卡片
    createFromHighlight: async (highlightId) => {
        set({ loading: true, error: null });
        
        try {
            const response = await api.post(`/knowledge/cards/from-highlight/${highlightId}`);
            
            // 更新列表
            const { cards, totalCount } = get();
            set({
                cards: [response.data, ...cards],
                totalCount: totalCount + 1,
                loading: false
            });
            
            return response.data;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '从高亮创建知识卡片失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 从问答创建知识卡片
    createFromChat: async (content, paperId = null) => {
        set({ loading: true, error: null });
        
        try {
            const response = await api.post('/knowledge/cards/from-chat', {
                content,
                paper_id: paperId
            });
            
            // 更新列表
            const { cards, totalCount } = get();
            set({
                cards: [response.data, ...cards],
                totalCount: totalCount + 1,
                loading: false
            });
            
            return response.data;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '从问答创建知识卡片失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 搜索知识卡片
    searchCards: async (query, topK = 10) => {
        if (!query.trim()) {
            set({ searchResults: [] });
            return [];
        }
        
        set({ loading: true, error: null });
        
        try {
            const response = await api.get(`/knowledge/search?query=${encodeURIComponent(query)}&top_k=${topK}`);
            set({
                searchResults: response.data.results,
                loading: false
            });
            return response.data.results;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '搜索知识卡片失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 获取知识图谱数据
    fetchGraphData: async () => {
        set({ loading: true, error: null });
        
        try {
            const response = await api.get('/knowledge/graph');
            set({
                graphData: response.data,
                loading: false
            });
            return response.data;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '获取知识图谱数据失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 获取统计信息
    fetchStats: async () => {
        set({ loading: true, error: null });
        
        try {
            const response = await api.get('/knowledge/stats');
            set({
                stats: response.data,
                loading: false
            });
            return response.data;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '获取统计信息失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 自动发现关联
    findRelations: async (cardId) => {
        set({ loading: true, error: null });
        
        try {
            const response = await api.post(`/knowledge/cards/${cardId}/find-relations`);
            set({ loading: false });
            return response.data.relations;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '发现关联失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 获取卡片关联
    fetchCardRelations: async (cardId) => {
        set({ loading: true, error: null });
        
        try {
            const response = await api.get(`/knowledge/cards/${cardId}/relations`);
            set({ loading: false });
            return response.data;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '获取关联失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 创建关联
    createRelation: async (sourceCardId, targetCardId, relationType, description = '', confidence = 0.8) => {
        set({ loading: true, error: null });
        
        try {
            const response = await api.post(`/knowledge/relations?source_card_id=${sourceCardId}`, {
                target_card_id: targetCardId,
                relation_type: relationType,
                description,
                confidence
            });
            set({ loading: false });
            return response.data;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '创建关联失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 删除关联
    deleteRelation: async (relationId) => {
        set({ loading: true, error: null });
        
        try {
            await api.delete(`/knowledge/relations/${relationId}`);
            set({ loading: false });
            return true;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '删除关联失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 自动生成标签
    autoTag: async (cardId) => {
        set({ loading: true, error: null });
        
        try {
            const response = await api.post(`/knowledge/cards/${cardId}/auto-tag`);
            
            // 更新当前卡片
            const { currentCard, cards } = get();
            if (currentCard?.id === cardId) {
                set({
                    currentCard: { ...currentCard, tags: response.data.tags }
                });
            }
            
            // 更新列表中的卡片
            const updatedCards = cards.map(c =>
                c.id === cardId ? { ...c, tags: response.data.tags } : c
            );
            set({ cards: updatedCards, loading: false });
            
            return response.data.tags;
        } catch (error) {
            set({
                error: error.response?.data?.detail || '自动生成标签失败',
                loading: false
            });
            throw error;
        }
    },
    
    // 设置当前卡片
    setCurrentCard: (card) => set({ currentCard: card }),
    
    // 清除当前卡片
    clearCurrentCard: () => set({ currentCard: null }),
    
    // 重置状态
    reset: () => set({
        cards: [],
        totalCount: 0,
        currentCard: null,
        searchResults: [],
        graphData: null,
        stats: null,
        loading: false,
        error: null,
        currentPage: 1,
        filters: {
            category: null,
            sourceType: null,
            tag: null,
            search: ''
        }
    })
}));

export default useKnowledgeStore;

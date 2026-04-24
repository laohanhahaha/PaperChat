import { create } from 'zustand';
import { knowledgeApi } from '../api/knowledgeApi';
import { fetchWithCache, invalidateByPrefix } from '../hooks/useApiCache';

interface KnowledgeCard {
  id: number | string;
  tags?: string[];
  [key: string]: any;
}

interface KnowledgeFilters {
  category: string | null;
  sourceType: string | null;
  tag: string | null;
  search: string;
}

interface KnowledgeState {
    cards: KnowledgeCard[];
    totalCount: number;
    currentCard: KnowledgeCard | null;
    searchResults: any[];
    graphData: any;
    stats: any;
    loading: boolean;
    error: string | null;
    currentPage: number;
    pageSize: number;
    filters: KnowledgeFilters;

    setLoading: (loading: boolean) => void;
    clearError: () => void;
    setFilters: (filters: Partial<KnowledgeFilters>) => void;
    clearFilters: () => void;
    fetchCards: (params?: Record<string, any>) => Promise<any>;
    fetchCard: (cardId: number | string) => Promise<any>;
    createCard: (data: Record<string, any>) => Promise<any>;
    updateCard: (cardId: number | string, data: Record<string, any>) => Promise<any>;
    deleteCard: (cardId: number | string) => Promise<boolean>;
    createFromHighlight: (highlightId: number | string) => Promise<any>;
    createFromChat: (content: string, paperId?: number | null) => Promise<any>;
    searchCards: (query: string, topK?: number) => Promise<any[]>;
    fetchGraphData: () => Promise<any>;
    fetchStats: () => Promise<any>;
    findRelations: (cardId: number | string) => Promise<any>;
    fetchCardRelations: (cardId: number | string) => Promise<any>;
    createRelation: (sourceCardId: number | string, targetCardId: number | string, relationType: string, description?: string, confidence?: number) => Promise<any>;
    deleteRelation: (relationId: number | string) => Promise<boolean>;
    autoTag: (cardId: number | string) => Promise<any>;
    setCurrentCard: (card: KnowledgeCard | null) => void;
    clearCurrentCard: () => void;
    reset: () => void;
}

const useKnowledgeStore = create<KnowledgeState>((set, get) => ({
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
    
    // 获取知识卡片列表（使用 fetchWithCache + 请求去重）
    fetchCards: async (params = {}) => {
        const { currentPage, pageSize, filters } = get();
        
        set({ loading: true, error: null });
        
        const apiParams = {
            page: params.page || currentPage,
            page_size: params.pageSize || pageSize,
            search: filters.search,
            category: filters.category ?? undefined,
            source_type: filters.sourceType ?? undefined,
            tag: filters.tag ?? undefined
        };
        
        const cacheKey = `knowledge:cards:${JSON.stringify(apiParams)}`;
        
        try {
            interface CardsResponseData { cards: KnowledgeCard[]; total: number; page: number; page_size: number; }
            const data = await fetchWithCache<CardsResponseData>(
                cacheKey,
                () => knowledgeApi.getCards(apiParams).then(r => r.data)
            );
            
            set({
                cards: data.cards,
                totalCount: data.total,
                currentPage: data.page,
                pageSize: data.page_size,
                loading: false
            });
            
            return data;
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '获取知识卡片失败';
            set({
                error: errMsg,
                loading: false
            });
            throw error;
        }
    },
    
    // 获取单张卡片详情
    fetchCard: async (cardId) => {
        set({ loading: true, error: null });
        
        try {
            const response = await knowledgeApi.getCard(cardId);
            set({ currentCard: response.data, loading: false });
            return response.data;
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '获取卡片详情失败';
            set({
                error: errMsg,
                loading: false
            });
            throw error;
        }
    },
    
    // 创建知识卡片
    createCard: async (data) => {
        set({ loading: true, error: null });
        
        try {
            const response = await knowledgeApi.createCard(data);
            
            // 更新列表
            const { cards, totalCount } = get();
            set({
                cards: [response.data, ...cards],
                totalCount: totalCount + 1,
                loading: false
            });
            invalidateByPrefix('knowledge:cards:');
            
            return response.data;
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '创建知识卡片失败';
            set({
                error: errMsg,
                loading: false
            });
            throw error;
        }
    },
    
    // 更新知识卡片
    updateCard: async (cardId, data) => {
        set({ loading: true, error: null });
        
        try {
            const response = await knowledgeApi.updateCard(cardId, data);
            
            // 更新列表中的卡片
            const { cards, currentCard } = get();
            const updatedCards = cards.map(c => 
                c.id === cardId ? response.data : c
            );
            
            invalidateByPrefix('knowledge:cards:');
            set({
                cards: updatedCards,
                currentCard: currentCard?.id === cardId ? response.data : currentCard,
                loading: false
            });
            
            return response.data;
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '更新知识卡片失败';
            set({
                error: errMsg,
                loading: false
            });
            throw error;
        }
    },
    
    // 删除知识卡片
    deleteCard: async (cardId) => {
        set({ loading: true, error: null });
        
        try {
            await knowledgeApi.deleteCard(cardId);
            
            // 从列表中移除
            const { cards, totalCount, currentCard } = get();
            invalidateByPrefix('knowledge:cards:');
            set({
                cards: cards.filter(c => c.id !== cardId),
                totalCount: totalCount - 1,
                currentCard: currentCard?.id === cardId ? null : currentCard,
                loading: false
            });
            
            return true;
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '删除知识卡片失败';
            set({
                error: errMsg,
                loading: false
            });
            throw error;
        }
    },
    
    // 从高亮创建知识卡片
    createFromHighlight: async (highlightId) => {
        set({ loading: true, error: null });
        
        try {
            const response = await knowledgeApi.createFromHighlight(highlightId);
            
            // 更新列表
            const { cards, totalCount } = get();
            invalidateByPrefix('knowledge:cards:');
            set({
                cards: [response.data, ...cards],
                totalCount: totalCount + 1,
                loading: false
            });
            
            return response.data;
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '从高亮创建知识卡片失败';
            set({
                error: errMsg,
                loading: false
            });
            throw error;
        }
    },
    
    // 从问答创建知识卡片
    createFromChat: async (content, paperId = null) => {
        set({ loading: true, error: null });
        
        try {
            const response = await knowledgeApi.createFromChat(content, paperId);
            
            // 更新列表
            const { cards, totalCount } = get();
            invalidateByPrefix('knowledge:cards:');
            set({
                cards: [response.data, ...cards],
                totalCount: totalCount + 1,
                loading: false
            });
            
            return response.data;
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '从问答创建知识卡片失败';
            set({
                error: errMsg,
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
            const response = await knowledgeApi.searchCards(query, topK);
            set({
                searchResults: response.data.results,
                loading: false
            });
            return response.data.results;
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '搜索知识卡片失败';
            set({
                error: errMsg,
                loading: false
            });
            throw error;
        }
    },
    
    // 获取知识图谱数据
    fetchGraphData: async () => {
        set({ loading: true, error: null });
        
        try {
            const response = await knowledgeApi.getGraphData();
            set({
                graphData: response.data,
                loading: false
            });
            return response.data;
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '获取知识图谱数据失败';
            set({
                error: errMsg,
                loading: false
            });
            throw error;
        }
    },
    
    // 获取统计信息
    fetchStats: async () => {
        set({ loading: true, error: null });
        
        try {
            const response = await knowledgeApi.getStats();
            set({
                stats: response.data,
                loading: false
            });
            return response.data;
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '获取统计信息失败';
            set({
                error: errMsg,
                loading: false
            });
            throw error;
        }
    },
    
    // 自动发现关联
    findRelations: async (cardId) => {
        set({ loading: true, error: null });
        
        try {
            const response = await knowledgeApi.findRelations(cardId);
            set({ loading: false });
            return response.data.relations;
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '发现关联失败';
            set({
                error: errMsg,
                loading: false
            });
            throw error;
        }
    },
    
    // 获取卡片关联
    fetchCardRelations: async (cardId) => {
        set({ loading: true, error: null });
        
        try {
            const response = await knowledgeApi.getCardRelations(cardId);
            set({ loading: false });
            return response.data;
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '获取关联失败';
            set({
                error: errMsg,
                loading: false
            });
            throw error;
        }
    },
    
    // 创建关联
    createRelation: async (sourceCardId, targetCardId, relationType, description = '', confidence = 0.8) => {
        set({ loading: true, error: null });
        
        try {
            const response = await knowledgeApi.createRelation(
                sourceCardId, targetCardId, relationType, description, confidence
            );
            set({ loading: false });
            return response.data;
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '创建关联失败';
            set({
                error: errMsg,
                loading: false
            });
            throw error;
        }
    },
    
    // 删除关联
    deleteRelation: async (relationId) => {
        set({ loading: true, error: null });
        
        try {
            await knowledgeApi.deleteRelation(relationId);
            set({ loading: false });
            return true;
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '删除关联失败';
            set({
                error: errMsg,
                loading: false
            });
            throw error;
        }
    },
    
    // 自动生成标签
    autoTag: async (cardId) => {
        set({ loading: true, error: null });
        
        try {
            const response = await knowledgeApi.autoTag(cardId);
            
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
        } catch (error: unknown) {
            const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '自动生成标签失败';
            set({
                error: errMsg,
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

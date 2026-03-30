import { create } from 'zustand';
import api from '../api';

const useChatStore = create((set, get) => ({
    // 状态
    sessions: [],
    currentSessionId: null,
    messages: [],
    sources: [],  // 当前最新回答的引用来源
    isLoading: false,
    error: null,
    
    // 跨文档问答状态
    selectedPaperIds: [],  // 当前选中的论文ID列表（跨文档问答）
    crossDocSources: [],   // 跨文档问答的引用来源
    isCrossDocMode: false, // 是否处于跨文档问答模式
    
    // 联网搜索状态
    enableSearch: false,   // 是否启用联网搜索
    searchStatus: null,    // null | 'searching' | 'completed'

    // 获取会话列表
    fetchSessions: async (paperId = null) => {
        set({ isLoading: true, error: null });
        try {
            const params = paperId ? { paper_id: paperId } : {};
            const response = await api.get('/chat/sessions', { params });
            set({ 
                sessions: response.data.sessions || [],
                isLoading: false 
            });
            return response.data.sessions;
        } catch (error) {
            console.error('获取会话列表失败:', error);
            set({ 
                error: error.response?.data?.detail || '获取会话列表失败',
                isLoading: false 
            });
            return [];
        }
    },

    // 创建新会话
    createSession: async (paperId = null, title = '新对话') => {
        set({ isLoading: true, error: null });
        try {
            const response = await api.post('/chat/sessions', null, {
                params: { paper_id: paperId, title }
            });
            const newSession = response.data;
            
            set(state => ({
                sessions: [newSession, ...state.sessions],
                currentSessionId: newSession.id,
                messages: [],
                sources: [],
                isLoading: false
            }));
            
            return newSession;
        } catch (error) {
            console.error('创建会话失败:', error);
            set({ 
                error: error.response?.data?.detail || '创建会话失败',
                isLoading: false 
            });
            return null;
        }
    },

    // 获取或创建论文的默认会话
    getOrCreateSessionByPaper: async (paperId) => {
        set({ isLoading: true, error: null });
        try {
            const response = await api.get(`/chat/sessions/by-paper/${paperId}`);
            const session = response.data;
            
            // 如果是新会话，添加到列表开头
            if (session.is_new) {
                set(state => ({
                    sessions: [session, ...state.sessions],
                    currentSessionId: session.id,
                    isLoading: false
                }));
            } else {
                // 确保会话在列表中
                set(state => {
                    const exists = state.sessions.find(s => s.id === session.id);
                    if (!exists) {
                        return {
                            sessions: [session, ...state.sessions],
                            currentSessionId: session.id,
                            isLoading: false
                        };
                    }
                    return {
                        currentSessionId: session.id,
                        isLoading: false
                    };
                });
            }
            
            // 加载会话消息
            await get().fetchMessages(session.id);
            
            return session;
        } catch (error) {
            console.error('获取/创建会话失败:', error);
            set({ 
                error: error.response?.data?.detail || '获取会话失败',
                isLoading: false 
            });
            return null;
        }
    },

    // 删除会话
    deleteSession: async (sessionId) => {
        set({ isLoading: true, error: null });
        try {
            await api.delete(`/chat/sessions/${sessionId}`);
            
            set(state => {
                const newSessions = state.sessions.filter(s => s.id !== sessionId);
                // 如果删除的是当前会话，重置当前会话
                const newCurrentSessionId = state.currentSessionId === sessionId 
                    ? (newSessions.length > 0 ? newSessions[0].id : null)
                    : state.currentSessionId;
                
                return {
                    sessions: newSessions,
                    currentSessionId: newCurrentSessionId,
                    messages: state.currentSessionId === sessionId ? [] : state.messages,
                    sources: state.currentSessionId === sessionId ? [] : state.sources,
                    isLoading: false
                };
            });
            
            return true;
        } catch (error) {
            console.error('删除会话失败:', error);
            set({ 
                error: error.response?.data?.detail || '删除会话失败',
                isLoading: false 
            });
            return false;
        }
    },

    // 更新会话标题
    updateSessionTitle: async (sessionId, title) => {
        try {
            const response = await api.put(`/chat/sessions/${sessionId}`, null, {
                params: { title }
            });
            
            set(state => ({
                sessions: state.sessions.map(s => 
                    s.id === sessionId 
                        ? { ...s, title: response.data.title }
                        : s
                )
            }));
            
            return true;
        } catch (error) {
            console.error('更新会话标题失败:', error);
            return false;
        }
    },

    // 设置当前会话
    setCurrentSession: (sessionId) => {
        set({ 
            currentSessionId: sessionId,
            sources: [] // 切换会话时清空来源
        });
    },

    // 获取会话消息
    fetchMessages: async (sessionId) => {
        if (!sessionId) return [];
        
        set({ isLoading: true, error: null });
        try {
            const response = await api.get(`/chat/sessions/${sessionId}/messages`);
            const messages = response.data.messages || [];
            
            // 转换为前端格式
            const formattedMessages = messages.map(m => ({
                id: m.id,
                role: m.role,
                content: m.content,
                sources: m.sources
            }));
            
            set({ 
                messages: formattedMessages,
                isLoading: false 
            });
            
            return formattedMessages;
        } catch (error) {
            console.error('获取消息失败:', error);
            set({ 
                error: error.response?.data?.detail || '获取消息失败',
                isLoading: false 
            });
            return [];
        }
    },

    // 添加本地消息（用于流式显示）
    addMessage: (message) => {
        set(state => ({
            messages: [...state.messages, message]
        }));
    },

    // 更新最后一条消息（用于流式输出）
    updateLastMessage: (content) => {
        set(state => {
            if (state.messages.length === 0) return state;
            
            const updated = [...state.messages];
            const lastIndex = updated.length - 1;
            updated[lastIndex] = {
                ...updated[lastIndex],
                content: content
            };
            return { messages: updated };
        });
    },

    // 设置引用来源
    setSources: (sources) => {
        set({ sources });
    },

    // 清空当前会话的消息
    clearMessages: () => {
        set({ messages: [], sources: [] });
    },

    // 重置状态
    reset: () => {
        set({
            sessions: [],
            currentSessionId: null,
            messages: [],
            sources: [],
            isLoading: false,
            error: null,
            selectedPaperIds: [],
            crossDocSources: [],
            isCrossDocMode: false,
            enableSearch: false,
            searchStatus: null
        });
    },

    // ============ 联网搜索相关方法 ============
    
    // 切换联网搜索
    toggleSearch: () => {
        set(state => ({ enableSearch: !state.enableSearch }));
    },
    
    // 设置搜索状态
    setSearchStatus: (status) => {
        set({ searchStatus: status });
    },
    
    // 清空搜索状态
    clearSearchState: () => {
        set({ searchStatus: null });
    },

    // ============ 跨文档问答相关方法 ============
    
    // 添加论文到跨文档选择
    addPaperToCrossDoc: (paperId) => {
        set(state => {
            if (state.selectedPaperIds.includes(paperId)) {
                return state; // 已存在，不重复添加
            }
            return {
                selectedPaperIds: [...state.selectedPaperIds, paperId],
                isCrossDocMode: true
            };
        });
    },

    // 从跨文档选择中移除论文
    removePaperFromCrossDoc: (paperId) => {
        set(state => {
            const newPaperIds = state.selectedPaperIds.filter(id => id !== paperId);
            return {
                selectedPaperIds: newPaperIds,
                isCrossDocMode: newPaperIds.length > 0
            };
        });
    },

    // 清空跨文档选择
    clearCrossDocPapers: () => {
        set({
            selectedPaperIds: [],
            crossDocSources: [],
            isCrossDocMode: false
        });
    },

    // 设置跨文档选择（批量）
    setCrossDocPapers: (paperIds) => {
        set({
            selectedPaperIds: paperIds,
            isCrossDocMode: paperIds.length > 0
        });
    },

    // 设置跨文档引用来源
    setCrossDocSources: (sources) => {
        set({ crossDocSources: sources });
    },

    // 创建跨文档会话
    createCrossDocSession: async (paperIds, title = '跨文档对话') => {
        set({ isLoading: true, error: null });
        try {
            const response = await api.post('/chat/sessions/cross-doc', paperIds, {
                params: { title }
            });
            const newSession = response.data;
            
            set(state => ({
                sessions: [newSession, ...state.sessions],
                currentSessionId: newSession.id,
                selectedPaperIds: paperIds,
                isCrossDocMode: true,
                messages: [],
                sources: [],
                crossDocSources: [],
                isLoading: false
            }));
            
            return newSession;
        } catch (error) {
            console.error('创建跨文档会话失败:', error);
            set({ 
                error: error.response?.data?.detail || '创建跨文档会话失败',
                isLoading: false 
            });
            return null;
        }
    }
}));

export default useChatStore;

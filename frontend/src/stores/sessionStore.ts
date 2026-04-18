import { create } from 'zustand';
import { chatApi } from '../api/chatApi';

interface Session {
  id: number | string;
  title: string;
  paper_id?: number | null;
  is_new?: boolean;
  [key: string]: any;
}

interface CachedData<T> {
  data: T;
  timestamp: number;
}

interface SessionState {
  sessions: Session[];
  currentSessionId: number | string | null;
  sessionsLoading: boolean;
  error: string | null;
  sessionCache: Record<string, CachedData<Session[]>>;

  _getSessionCacheKey: (paperId?: number | null) => string;
  fetchSessions: (paperId?: number | null, forceRefresh?: boolean) => Promise<Session[]>;
  invalidateSessionCache: (paperId?: number | null) => void;
  clearSessionCache: () => void;
  createSession: (paperId?: number | null, title?: string) => Promise<Session | undefined>;
  getOrCreateSessionByPaper: (paperId: number | string) => Promise<Session | null>;
  deleteSession: (sessionId: number | string) => Promise<boolean>;
  renameSession: (sessionId: number | string, newTitle: string) => Promise<boolean>;
  autoNameSession: (sessionId: number | string, firstMessage: string) => Promise<boolean>;
  updateSessionTitle: (sessionId: number | string, title: string) => Promise<boolean>;
  setCurrentSession: (sessionId: number | string | null) => void;
  fetchSessionsByPaper: (paperId: number | string) => Promise<Session[]>;
  createCrossDocSession: (paperIds: number[], title?: string) => Promise<Session | null>;
  clearError: () => void;
  reset: () => void;
}

const CACHE_TTL = 5 * 60 * 1000; // 5 分钟缓存过期时间

export const useSessionStore = create<SessionState>((set, get) => ({
  // 状态
  sessions: [],
  currentSessionId: null,
  sessionsLoading: false,
  error: null,
  
  // 会话列表缓存: { [cacheKey]: { data, timestamp } }
  // cacheKey 格式: 'all' 或 `paper_${paperId}`
  sessionCache: {},

  // 获取缓存键
  _getSessionCacheKey: (paperId = null) => paperId ? `paper_${paperId}` : 'all',
  
  // 获取会话列表（带缓存）
  fetchSessions: async (paperId = null, forceRefresh = false) => {
    const cacheKey = get()._getSessionCacheKey(paperId);
    const cached = get().sessionCache[cacheKey];
    
    // 检查缓存
    if (!forceRefresh && cached && (Date.now() - cached.timestamp < CACHE_TTL)) {
      set({ 
        sessions: cached.data,
        sessionsLoading: false 
      });
      return cached.data;
    }
    
    set({ sessionsLoading: true, error: null });
    try {
      const params = paperId ? { paper_id: paperId } : {};
      const response = await chatApi.getSessions(params);
      const sessions = response.data.sessions || [];
      
      set(state => ({ 
        sessions: sessions,
        sessionCache: {
          ...state.sessionCache,
          [cacheKey]: { data: sessions, timestamp: Date.now() }
        },
        sessionsLoading: false 
      }));
      return sessions;
    } catch (error: any) {
      console.error('获取会话列表失败:', error);
      set({ 
        error: error.response?.data?.detail || '获取会话列表失败',
        sessionsLoading: false 
      });
      return [];
    }
  },
  
  // 清除指定缓存
  invalidateSessionCache: (paperId = null) => {
    const cacheKey = get()._getSessionCacheKey(paperId);
    set(state => {
      const newCache = { ...state.sessionCache };
      delete newCache[cacheKey];
      return { sessionCache: newCache };
    });
  },
  
  // 清除所有会话缓存
  clearSessionCache: () => {
    set({ sessionCache: {} });
  },

  // 创建新会话
  createSession: async (paperId = null, title = '新对话') => {
    set({ sessionsLoading: true, error: null });
    try {
      const response = await chatApi.createSession(paperId, title);
      const newSession = response.data;

      set(state => {
        // 清除相关缓存
        const newCache = { ...state.sessionCache };
        delete newCache['all'];
        if (paperId) delete newCache[`paper_${paperId}`];
        
        return {
          sessions: [newSession, ...state.sessions],
          currentSessionId: newSession.id,
          sessionCache: newCache,
          sessionsLoading: false
        };
      });

      return newSession;
    } catch (error: any) {
      console.error('创建会话失败:', error);
      set({
        error: error.response?.data?.detail || '创建会话失败',
        sessionsLoading: false
      });
      throw error;
    }
  },

  // 获取或创建论文的默认会话
  getOrCreateSessionByPaper: async (paperId) => {
    set({ sessionsLoading: true, error: null });
    try {
      const response = await chatApi.getSessionsByPaper(paperId);
      const session = response.data;
      
      // 如果是新会话，添加到列表开头
      if (session.is_new) {
        set(state => ({
          sessions: [session, ...state.sessions],
          currentSessionId: session.id,
          sessionsLoading: false
        }));
      } else {
        // 确保会话在列表中
        set(state => {
          const exists = state.sessions.find(s => s.id === session.id);
          if (!exists) {
            return {
              sessions: [session, ...state.sessions],
              currentSessionId: session.id,
              sessionsLoading: false
            };
          }
          return {
            currentSessionId: session.id,
            sessionsLoading: false
          };
        });
      }
      
      return session;
    } catch (error: any) {
      console.error('获取/创建会话失败:', error);
      set({ 
        error: error.response?.data?.detail || '获取会话失败',
        sessionsLoading: false 
      });
      return null;
    }
  },

  // 删除会话
  deleteSession: async (sessionId) => {
    set({ sessionsLoading: true, error: null });
    try {
      await chatApi.deleteSession(sessionId);
      
      set(state => {
        const newSessions = state.sessions.filter(s => s.id !== sessionId);
        // 如果删除的是当前会话，重置当前会话
        const newCurrentSessionId = state.currentSessionId === sessionId 
          ? (newSessions.length > 0 ? newSessions[0].id : null)
          : state.currentSessionId;
        
        // 清除所有缓存（因为不确定影响哪些缓存）
        return {
          sessions: newSessions,
          currentSessionId: newCurrentSessionId,
          sessionCache: {},
          sessionsLoading: false
        };
      });
      
      return true;
    } catch (error: any) {
      console.error('删除会话失败:', error);
      set({ 
        error: error.response?.data?.detail || '删除会话失败',
        sessionsLoading: false 
      });
      return false;
    }
  },

  // 更新会话标题（重命名）
  renameSession: async (sessionId, newTitle) => {
    try {
      const response = await chatApi.renameSession(sessionId, newTitle);
      
      set(state => ({
        sessions: state.sessions.map(s => 
          s.id === sessionId 
            ? { ...s, title: response.data.title }
            : s
        )
      }));
      
      return true;
    } catch (error: any) {
      console.error('重命名会话失败:', error);
      return false;
    }
  },

  // 自动命名会话（基于第一条消息内容）
  autoNameSession: async (sessionId, firstMessage) => {
    if (!firstMessage || !sessionId) return false;
    
    // 清理消息内容：去掉换行符，取前20个字符
    const cleanedMessage = firstMessage.replace(/\n/g, ' ').trim();
    const newTitle = cleanedMessage.length > 20 
      ? cleanedMessage.slice(0, 20) + '...' 
      : cleanedMessage;
    
    if (!newTitle) return false;
    
    return await get().renameSession(sessionId, newTitle);
  },

  // 更新会话标题（兼容旧方法名）
  updateSessionTitle: async (sessionId, title) => {
    return await get().renameSession(sessionId, title);
  },

  // 设置当前会话
  setCurrentSession: (sessionId) => {
    set({ currentSessionId: sessionId });
  },

  // 获取某论文的会话列表
  fetchSessionsByPaper: async (paperId) => {
    return await get().fetchSessions(paperId);
  },

  // 创建跨文档会话
  createCrossDocSession: async (paperIds, title = '跨文档对话') => {
    set({ sessionsLoading: true, error: null });
    try {
      const { chatApi } = await import('../api/chatApi');
      const response = await chatApi.createCrossDocSession(paperIds, title);
      const newSession = response.data;
      
      set(state => {
        // 清除所有缓存
        const newCache = { ...state.sessionCache };
        delete newCache['all'];
        paperIds.forEach(pid => delete newCache[`paper_${pid}`]);
        
        return {
          sessions: [newSession, ...state.sessions],
          currentSessionId: newSession.id,
          sessionCache: newCache,
          sessionsLoading: false
        };
      });
      
      return newSession;
    } catch (error: any) {
      console.error('创建跨文档会话失败:', error);
      set({ 
        error: error.response?.data?.detail || '创建跨文档会话失败',
        sessionsLoading: false 
      });
      return null;
    }
  },

  // 清除错误
  clearError: () => set({ error: null }),

  // 重置状态
  reset: () => set({
    sessions: [],
    currentSessionId: null,
    sessionsLoading: false,
    error: null,
    sessionCache: {}
  })
}));

export default useSessionStore;

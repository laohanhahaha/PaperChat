import { create } from 'zustand';
import { chatApi } from '../api/chatApi';

interface Message {
  id: number | string;
  role: string;
  content: string;
  sources?: any;
  [key: string]: any;
}

interface CachedMessages {
  messages: Message[];
  timestamp: number;
}

interface MessageState {
  messages: Message[];
  messagesLoading: boolean;
  sources: any[];
  crossDocSources: any[];
  streamingMessage: string;
  isStreaming: boolean;
  error: string | null;
  messageCache: Record<string, CachedMessages>;
  hasMore: boolean;
  loadingMore: boolean;
  pageSize: number;

  fetchMessages: (sessionId: number | string, reset?: boolean) => Promise<Message[]>;
  loadMoreMessages: (sessionId: number | string) => Promise<Message[]>;
  loadMessagesFromCache: (sessionId: number | string) => Message[] | null;
  invalidateMessageCache: (sessionId: number | string) => void;
  clearMessageCache: () => void;
  addMessage: (message: Message) => void;
  updateLastMessage: (content: string) => void;
  updateStreamingMessage: (content: string) => void;
  setIsStreaming: (isStreaming: boolean) => void;
  setSources: (sources: any[]) => void;
  setCrossDocSources: (sources: any[]) => void;
  clearMessages: () => void;
  clearError: () => void;
  reset: () => void;
}

const CACHE_TTL = 5 * 60 * 1000; // 5 分钟缓存过期时间
const DEFAULT_PAGE_SIZE = 50; // 默认每页消息数

export const useMessageStore = create<MessageState>((set, get) => ({
  // 状态
  messages: [],
  messagesLoading: false,
  sources: [],  // 当前最新回答的引用来源
  crossDocSources: [],  // 跨文档问答的引用来源
  streamingMessage: '',
  isStreaming: false,
  error: null,
  
  // 消息缓存: { [sessionId]: { messages, timestamp } }
  messageCache: {},
  
  // 分页状态
  hasMore: true,        // 是否有更多历史消息
  loadingMore: false,   // 是否正在加载更多
  pageSize: DEFAULT_PAGE_SIZE,  // 每页消息数

  // 获取会话消息（支持分页和缓存）
  fetchMessages: async (sessionId, reset = true) => {
    if (!sessionId) return [];
    
    const { pageSize } = get();
    
    if (reset) {
      set({ messages: [], hasMore: true, messagesLoading: true, error: null });
    }
    
    const offset = reset ? 0 : get().messages.length;
    
    try {
      const response = await chatApi.getMessages(sessionId, { 
        limit: pageSize, 
        offset 
      });
      
      const newMessages = response.data.messages || [];
      const total = response.data.total || 0;
      
      // 后端返回的是倒序（最新在前），需要 reverse 变成正序（最新在底部）
      const formattedMessages: Message[] = newMessages.map((m: any) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        sources: m.sources
      }));
      const orderedMessages = formattedMessages.reverse();
      
      set(state => ({
        messages: reset ? orderedMessages : [...state.messages, ...orderedMessages],
        hasMore: total > (reset ? orderedMessages.length : state.messages.length + orderedMessages.length),
        messagesLoading: false,
        // 更新缓存
        messageCache: {
          ...state.messageCache,
          [sessionId]: { 
            messages: reset ? orderedMessages : [...state.messages, ...orderedMessages], 
            timestamp: Date.now() 
          }
        }
      }));
      
      return orderedMessages;
    } catch (error: any) {
      console.error('获取消息失败:', error);
      set({ 
        error: error.response?.data?.detail || '获取消息失败',
        messagesLoading: false 
      });
      return [];
    }
  },
  
  // 加载更多历史消息
  loadMoreMessages: async (sessionId) => {
    if (!sessionId || !get().hasMore || get().loadingMore) return [];
    
    set({ loadingMore: true });
    const offset = get().messages.length;
    const { pageSize } = get();
    
    try {
      const response = await chatApi.getMessages(sessionId, {
        limit: pageSize,
        offset
      });
      
      const olderMessages = response.data.messages || [];
      const total = response.data.total || 0;
      
      // 后端返回的也是倒序，reverse 后追加到数组前面（更早的消息放前面）
      const formattedMessages: Message[] = olderMessages.map((m: any) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        sources: m.sources
      }));
      const orderedMessages = formattedMessages.reverse();
      
      set(state => {
        const updatedMessages = [...orderedMessages, ...state.messages];
        return {
          messages: updatedMessages,
          hasMore: updatedMessages.length < total,
          loadingMore: false,
          // 更新缓存
          messageCache: {
            ...state.messageCache,
            [sessionId]: { 
              messages: updatedMessages, 
              timestamp: Date.now() 
            }
          }
        };
      });
      
      return orderedMessages;
    } catch (error: any) {
      console.error('加载更多消息失败:', error);
      set({ loadingMore: false });
      return [];
    }
  },
  
  // 从缓存加载消息
  loadMessagesFromCache: (sessionId) => {
    const cached = get().messageCache[sessionId];
    if (cached && (Date.now() - cached.timestamp < CACHE_TTL)) {
      set({ 
        messages: cached.messages,
        messagesLoading: false 
      });
      return cached.messages;
    }
    return null;
  },
  
  // 清除指定会话的消息缓存
  invalidateMessageCache: (sessionId) => {
    set(state => {
      const newCache = { ...state.messageCache };
      delete newCache[sessionId];
      return { messageCache: newCache };
    });
  },
  
  // 清除所有消息缓存
  clearMessageCache: () => {
    set({ messageCache: {} });
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

  // 更新流式消息内容
  updateStreamingMessage: (content) => {
    set({ streamingMessage: content });
  },

  // 设置流式状态
  setIsStreaming: (isStreaming) => {
    set({ isStreaming });
  },

  // 设置引用来源
  setSources: (sources) => {
    set({ sources });
  },

  // 设置跨文档引用来源
  setCrossDocSources: (sources) => {
    set({ crossDocSources: sources });
  },

  // 清空当前会话的消息
  clearMessages: () => {
    set({ 
      messages: [], 
      sources: [], 
      crossDocSources: [], 
      streamingMessage: '',
      hasMore: true,
      loadingMore: false
    });
  },

  // 清除错误
  clearError: () => set({ error: null }),

  // 重置状态
  reset: () => set({
    messages: [],
    messagesLoading: false,
    sources: [],
    crossDocSources: [],
    streamingMessage: '',
    isStreaming: false,
    error: null,
    messageCache: {},
    hasMore: true,
    loadingMore: false
  })
}));

export default useMessageStore;

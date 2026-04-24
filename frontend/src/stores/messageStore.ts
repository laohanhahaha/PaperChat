import { create } from 'zustand';
import { chatApi } from '../api/chatApi';
import { fetchWithCache, invalidate, invalidateAll, invalidateByPrefix } from '../hooks/useApiCache';

interface AgentStep {
  type: 'thought' | 'action' | 'observation' | 'agent_thought' | 'agent_action' | 'agent_observation' | 'reflection';
  step: number;
  content?: string;
  tool?: string;
  input?: unknown;
  subAgent?: string;
}

interface Source {
  [key: string]: unknown;
}

interface Message {
  id: number | string;
  role: string;
  content: string;
  sources?: Source[];
  agentSteps?: AgentStep[];
  thinkingContent?: string;
  agentComplete?: boolean;
  toolResult?: unknown;
  [key: string]: unknown;
}

interface MessageState {
  messages: Message[];
  messagesLoading: boolean;
  sources: Source[];
  crossDocSources: Source[];
  streamingMessage: string;
  isStreaming: boolean;
  error: string | null;
  hasMore: boolean;
  loadingMore: boolean;
  pageSize: number;

  fetchMessages: (sessionId: number | string, reset?: boolean) => Promise<Message[]>;
  loadMoreMessages: (sessionId: number | string) => Promise<Message[]>;
  invalidateMessageCache: (sessionId: number | string) => void;
  clearMessageCache: () => void;
  addMessage: (message: Message) => void;
  updateLastMessage: (content: string) => void;
  setLastMessageToolResult: (toolResult: unknown) => void;
  addAgentStep: (step: AgentStep) => void;
  appendThinkingContent: (content: string) => void;
  markAgentComplete: () => void;
  updateStreamingMessage: (content: string) => void;
  setIsStreaming: (isStreaming: boolean) => void;
  setSources: (sources: Source[]) => void;
  setCrossDocSources: (sources: Source[]) => void;
  clearMessages: () => void;
  clearError: () => void;
  reset: () => void;
}

const DEFAULT_PAGE_SIZE = 50; // 默认每页消息数

// 缓存键生成函数
const msgCacheKey = (sessionId: number | string, offset: number, limit: number) =>
  `messages:${sessionId}:offset=${offset}:limit=${limit}`;

export const useMessageStore = create<MessageState>((set, get) => ({
  // 状态
  messages: [],
  messagesLoading: false,
  sources: [],  // 当前最新回答的引用来源
  crossDocSources: [],  // 跨文档问答的引用来源
  streamingMessage: '',
  isStreaming: false,
  error: null,
  
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
    const cacheKey = msgCacheKey(sessionId, offset, pageSize);
    
    try {
      interface MessagesResponseData {
        messages: Array<{ id: number | string; role: string; content: string; sources?: Source[] }>;
        total: number;
      }
      const data = await fetchWithCache<MessagesResponseData>(
        cacheKey,
        () => chatApi.getMessages(sessionId, { limit: pageSize, offset }).then(r => r.data)
      );
      
      const newMessages = data.messages || [];
      const total = data.total || 0;
      
      // 后端返回的是倒序（最新在前），需要 reverse 变成正序（最新在底部）
      const formattedMessages: Message[] = newMessages.map(m => ({
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
      }));
      
      return orderedMessages;
    } catch (error: unknown) {
      console.error('获取消息失败:', error);
      const errMsg = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail || '获取消息失败';
      set({ 
        error: errMsg,
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
    const cacheKey = msgCacheKey(sessionId, offset, pageSize);
    
    try {
      interface MessagesResponseData {
        messages: Array<{ id: number | string; role: string; content: string; sources?: Source[] }>;
        total: number;
      }
      const data = await fetchWithCache<MessagesResponseData>(
        cacheKey,
        () => chatApi.getMessages(sessionId, { limit: pageSize, offset }).then(r => r.data)
      );
      
      const olderMessages = data.messages || [];
      const total = data.total || 0;
      
      // 后端返回的也是倒序，reverse 后追加到数组前面（更早的消息放前面）
      const formattedMessages: Message[] = olderMessages.map(m => ({
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
        };
      });
      
      return orderedMessages;
    } catch (error: unknown) {
      console.error('加载更多消息失败:', error);
      set({ loadingMore: false });
      return [];
    }
  },
  
  // 清除指定会话的消息缓存（通过 useApiCache 失效）
  invalidateMessageCache: (sessionId) => {
    // 失效该 sessionId 下所有分页缓存
    invalidateByPrefix(`messages:${sessionId}:`);
  },
  
  // 清除所有消息缓存
  clearMessageCache: () => {
    invalidateAll();
  },

  // 添加本地消息（用于流式显示）
  addMessage: (message) => {
    set(state => ({
      messages: [...state.messages, message]
    }));
  },

  // 向最后一条 assistant 消息追加 agentStep
  addAgentStep: (step) => {
    set(state => {
      if (state.messages.length === 0) return state;
      const updated = [...state.messages];
      // 找到最后一条 assistant 消息
      let lastAssistantIdx = -1;
      for (let i = updated.length - 1; i >= 0; i--) {
        if (updated[i].role === 'assistant') { lastAssistantIdx = i; break; }
      }
      if (lastAssistantIdx === -1) return state;
      updated[lastAssistantIdx] = {
        ...updated[lastAssistantIdx],
        agentSteps: [...(updated[lastAssistantIdx].agentSteps || []), step],
      };
      return { messages: updated };
    });
  },

  // 追加深度思考内容到最后一条 assistant 消息
  appendThinkingContent: (content) => {
    set(state => {
      if (state.messages.length === 0) return state;
      const updated = [...state.messages];
      let lastAssistantIdx = -1;
      for (let i = updated.length - 1; i >= 0; i--) {
        if (updated[i].role === 'assistant') { lastAssistantIdx = i; break; }
      }
      if (lastAssistantIdx === -1) return state;
      updated[lastAssistantIdx] = {
        ...updated[lastAssistantIdx],
        thinkingContent: (updated[lastAssistantIdx].thinkingContent || '') + content,
      };
      return { messages: updated };
    });
  },

  // 标记 Agent 推理完成
  markAgentComplete: () => {
    set(state => {
      if (state.messages.length === 0) return state;
      const updated = [...state.messages];
      let lastAssistantIdx = -1;
      for (let i = updated.length - 1; i >= 0; i--) {
        if (updated[i].role === 'assistant') { lastAssistantIdx = i; break; }
      }
      if (lastAssistantIdx === -1) return state;
      updated[lastAssistantIdx] = {
        ...updated[lastAssistantIdx],
        agentComplete: true,
      };
      return { messages: updated };
    });
  },

  // 设置最后一条消息的工具结果
  setLastMessageToolResult: (toolResult) => {
    set(state => {
      if (state.messages.length === 0) return state;
      const updated = [...state.messages];
      const lastIndex = updated.length - 1;
      updated[lastIndex] = {
        ...updated[lastIndex],
        toolResult,
      };
      return { messages: updated };
    });
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
  reset: () => {
    invalidateAll();
    set({
      messages: [],
      messagesLoading: false,
      sources: [],
      crossDocSources: [],
      streamingMessage: '',
      isStreaming: false,
      error: null,
      hasMore: true,
      loadingMore: false
    });
  }
}));

export default useMessageStore;

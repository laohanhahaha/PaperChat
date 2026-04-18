// 兼容层：re-export 所有新 store 的内容，保证旧导入路径不报错
import { useSessionStore } from './sessionStore';
import { useMessageStore } from './messageStore';
import { useChatConfigStore } from './chatConfigStore';
import { create } from 'zustand';

interface ChatState {
  // 代理状态
  sessions: any[];
  currentSessionId: number | string | null;
  sessionsLoading: boolean;
  messages: any[];
  messagesLoading: boolean;
  sources: any[];
  crossDocSources: any[];
  selectedPaperIds: number[];
  isCrossDocMode: boolean;
  enableSearch: boolean;
  searchStatus: 'searching' | 'completed' | null;
  currentIntent: any;
  isLoading: boolean;
  error: string | null;
  hasMore: boolean;
  loadingMore: boolean;
  pageSize: number;
  sessionCache: any;
  messageCache: any;

  // 会话方法
  fetchSessions: (p?: any, force?: boolean) => Promise<any>;
  createSession: (p?: any, t?: string) => Promise<any>;
  getOrCreateSessionByPaper: (p: any) => Promise<any>;
  deleteSession: (id: any) => Promise<any>;
  renameSession: (id: any, t: string) => Promise<any>;
  autoNameSession: (id: any, m: string) => Promise<any>;
  updateSessionTitle: (id: any, t: string) => Promise<any>;
  setCurrentSession: (id: any) => void;
  createCrossDocSession: (ids: number[], t?: string) => Promise<any>;
  invalidateSessionCache: (p?: any) => void;
  clearSessionCache: () => void;

  // 消息方法
  fetchMessages: (id: any, reset?: boolean) => Promise<any>;
  addMessage: (m: any) => void;
  updateLastMessage: (c: string) => void;
  setSources: (s: any) => void;
  clearMessages: () => void;
  loadMoreMessages: (id: any) => Promise<any>;
  loadMessagesFromCache: (id: any) => any;
  invalidateMessageCache: (id: any) => void;
  clearMessageCache: () => void;

  // 跨文档方法
  addPaperToCrossDoc: (p: number) => void;
  removePaperFromCrossDoc: (p: number) => void;
  clearCrossDocPapers: () => void;
  setCrossDocPapers: (ids: number[]) => void;
  setCrossDocSources: (s: any) => void;

  // 搜索方法
  toggleSearch: () => void;
  setSearchStatus: (s: any) => void;
  clearSearchState: () => void;

  // 意图方法
  setCurrentIntent: (i: any) => void;
  clearCurrentIntent: () => void;

  // 重置
  reset: () => void;
}

const useChatStore = create<ChatState>(() => {
  const S = () => useSessionStore.getState();
  const M = () => useMessageStore.getState();
  const C = () => useChatConfigStore.getState();

  return {
    // 状态代理
    get sessions() { return S().sessions; },
    get currentSessionId() { return S().currentSessionId; },
    get sessionsLoading() { return S().sessionsLoading; },
    get messages() { return M().messages; },
    get messagesLoading() { return M().messagesLoading; },
    get sources() { return M().sources; },
    get crossDocSources() { return M().crossDocSources; },
    get selectedPaperIds() { return C().selectedPaperIds; },
    get isCrossDocMode() { return C().isCrossDocMode; },
    get enableSearch() { return C().enableSearch; },
    get searchStatus() { return C().searchStatus; },
    get currentIntent() { return C().currentIntent; },
    get isLoading() { return S().sessionsLoading || M().messagesLoading; },
    get error() { return S().error || M().error; },
    
    // 分页相关状态
    get hasMore() { return M().hasMore; },
    get loadingMore() { return M().loadingMore; },
    get pageSize() { return M().pageSize; },
    
    // 缓存相关状态
    get sessionCache() { return S().sessionCache; },
    get messageCache() { return M().messageCache; },

    // 会话方法
    fetchSessions: (p?, force?) => S().fetchSessions(p, force),
    createSession: (p?, t?) => S().createSession(p, t),
    getOrCreateSessionByPaper: (p) => S().getOrCreateSessionByPaper(p),
    deleteSession: (id) => S().deleteSession(id),
    renameSession: (id, t) => S().renameSession(id, t),
    autoNameSession: (id, m) => S().autoNameSession(id, m),
    updateSessionTitle: (id, t) => S().updateSessionTitle(id, t),
    setCurrentSession: (id) => S().setCurrentSession(id),
    createCrossDocSession: (ids, t?) => S().createCrossDocSession(ids, t),
    invalidateSessionCache: (p?) => S().invalidateSessionCache(p),
    clearSessionCache: () => S().clearSessionCache(),

    // 消息方法
    fetchMessages: (id, reset?) => M().fetchMessages(id, reset),
    addMessage: (m) => M().addMessage(m),
    updateLastMessage: (c) => M().updateLastMessage(c),
    setSources: (s) => M().setSources(s),
    clearMessages: () => M().clearMessages(),
    loadMoreMessages: (id) => M().loadMoreMessages(id),
    loadMessagesFromCache: (id) => M().loadMessagesFromCache(id),
    invalidateMessageCache: (id) => M().invalidateMessageCache(id),
    clearMessageCache: () => M().clearMessageCache(),

    // 跨文档方法
    addPaperToCrossDoc: (p) => C().addPaperToCrossDoc(p),
    removePaperFromCrossDoc: (p) => C().removePaperFromCrossDoc(p),
    clearCrossDocPapers: () => C().clearCrossDocPapers(),
    setCrossDocPapers: (ids) => C().setCrossDocPapers(ids),
    setCrossDocSources: (s) => { C().setCrossDocSources(s); M().setCrossDocSources(s); },

    // 搜索方法
    toggleSearch: () => C().toggleSearch(),
    setSearchStatus: (s) => C().setSearchStatus(s),
    clearSearchState: () => C().clearSearchState(),

    // 意图方法
    setCurrentIntent: (i) => C().setCurrentIntent(i),
    clearCurrentIntent: () => C().clearCurrentIntent(),

    // 重置
    reset: () => { S().reset(); M().reset(); C().reset(); }
  };
});

export default useChatStore;

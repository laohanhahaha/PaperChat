import { create } from 'zustand';

interface ChatConfigState {
  // 跨文档问答状态
  selectedPaperIds: number[];
  crossDocSources: any[];
  isCrossDocMode: boolean;

  // 联网搜索状态
  enableSearch: boolean;
  searchStatus: 'searching' | 'completed' | null;

  // 意图检测状态
  currentIntent: any;

  // 跨文档问答方法
  addPaperToCrossDoc: (paperId: number) => void;
  removePaperFromCrossDoc: (paperId: number) => void;
  clearCrossDocPapers: () => void;
  setCrossDocPapers: (paperIds: number[]) => void;
  togglePaper: (paperId: number) => void;
  setCrossDocSources: (sources: any[]) => void;
  setCrossDocMode: (isCrossDocMode: boolean) => void;

  // 联网搜索方法
  toggleSearch: () => void;
  setEnableSearch: (enable: boolean) => void;
  setSearchStatus: (status: 'searching' | 'completed' | null) => void;
  clearSearchState: () => void;

  // 意图检测方法
  setCurrentIntent: (intent: any) => void;
  clearCurrentIntent: () => void;
  setDetectedIntent: (intent: any) => void;

  // 配置重置
  resetConfig: () => void;
  reset: () => void;
}

export const useChatConfigStore = create<ChatConfigState>((set, get) => ({
  // 跨文档问答状态
  selectedPaperIds: [],  // 当前选中的论文ID列表（跨文档问答）
  crossDocSources: [],   // 跨文档问答的引用来源
  isCrossDocMode: false, // 是否处于跨文档问答模式
  
  // 联网搜索状态
  enableSearch: false,   // 是否启用联网搜索
  searchStatus: null,    // null | 'searching' | 'completed'

  // 意图检测状态
  currentIntent: null,

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

  // 切换论文选择（toggle）
  togglePaper: (paperId) => {
    set(state => {
      const exists = state.selectedPaperIds.includes(paperId);
      if (exists) {
        const newPaperIds = state.selectedPaperIds.filter(id => id !== paperId);
        return {
          selectedPaperIds: newPaperIds,
          isCrossDocMode: newPaperIds.length > 0
        };
      } else {
        return {
          selectedPaperIds: [...state.selectedPaperIds, paperId],
          isCrossDocMode: true
        };
      }
    });
  },

  // 设置跨文档引用来源
  setCrossDocSources: (sources) => {
    set({ crossDocSources: sources });
  },

  // 设置跨文档模式
  setCrossDocMode: (isCrossDocMode) => {
    set({ isCrossDocMode });
  },

  // ============ 联网搜索相关方法 ============
  
  // 切换联网搜索
  toggleSearch: () => {
    set(state => ({ enableSearch: !state.enableSearch }));
  },

  // 设置联网搜索启用状态
  setEnableSearch: (enable) => {
    set({ enableSearch: enable });
  },
  
  // 设置搜索状态
  setSearchStatus: (status) => {
    set({ searchStatus: status });
  },
  
  // 清空搜索状态
  clearSearchState: () => {
    set({ searchStatus: null });
  },

  // ============ 意图检测相关方法 ============

  // 设置当前意图
  setCurrentIntent: (intent) => {
    set({ currentIntent: intent });
  },

  // 清除意图
  clearCurrentIntent: () => {
    set({ currentIntent: null });
  },

  // 设置检测到的意图（兼容方法）
  setDetectedIntent: (intent) => {
    set({ currentIntent: intent });
  },

  // ============ 配置重置 ============

  // 重置配置
  resetConfig: () => {
    set({
      selectedPaperIds: [],
      crossDocSources: [],
      isCrossDocMode: false,
      enableSearch: false,
      searchStatus: null,
      currentIntent: null
    });
  },

  // 完整重置
  reset: () => {
    get().resetConfig();
  }
}));

export default useChatConfigStore;

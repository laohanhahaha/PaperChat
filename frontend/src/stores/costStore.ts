import { create } from 'zustand';
import costApi, {
  ModelInfo,
  SessionCost,
  MonthlyCost,
  BudgetStatus,
  CurrentModel,
} from '../api/costApi';

interface CostState {
  // 模型列表
  models: ModelInfo[];
  // 当前模型
  currentModel: CurrentModel | null;
  // 当前会话费用
  sessionCost: SessionCost | null;
  // 当月费用
  monthlyCost: MonthlyCost | null;
  // 预算状态
  budget: BudgetStatus | null;
  // 加载状态
  loading: {
    models: boolean;
    sessionCost: boolean;
    monthlyCost: boolean;
    budget: boolean;
    switching: boolean;
  };

  // Actions
  fetchModels: () => Promise<void>;
  fetchCurrentModel: () => Promise<void>;
  fetchSessionCost: (sessionId: string) => Promise<void>;
  fetchMonthlyCost: (year?: number, month?: number) => Promise<void>;
  fetchBudget: () => Promise<void>;
  setBudget: (monthlyLimit: number) => Promise<void>;
  switchModel: (model: string) => Promise<void>;
}

export const useCostStore = create<CostState>((set, get) => ({
  models: [],
  currentModel: null,
  sessionCost: null,
  monthlyCost: null,
  budget: null,
  loading: {
    models: false,
    sessionCost: false,
    monthlyCost: false,
    budget: false,
    switching: false,
  },

  fetchModels: async () => {
    set(s => ({ loading: { ...s.loading, models: true } }));
    try {
      const data = await costApi.getModels();
      set({ models: data.models });
    } catch (e) {
      // 静默失败
    } finally {
      set(s => ({ loading: { ...s.loading, models: false } }));
    }
  },

  fetchCurrentModel: async () => {
    try {
      const data = await costApi.getCurrentModel();
      set({ currentModel: data });
    } catch (e) {
      // 静默失败
    }
  },

  fetchSessionCost: async (sessionId: string) => {
    if (!sessionId) return;
    set(s => ({ loading: { ...s.loading, sessionCost: true } }));
    try {
      const data = await costApi.getSessionCost(sessionId);
      set({ sessionCost: data });
    } catch (e) {
      // 静默失败
    } finally {
      set(s => ({ loading: { ...s.loading, sessionCost: false } }));
    }
  },

  fetchMonthlyCost: async (year?: number, month?: number) => {
    set(s => ({ loading: { ...s.loading, monthlyCost: true } }));
    try {
      const data = await costApi.getMonthlyCost(year, month);
      set({ monthlyCost: data });
    } catch (e) {
      // 静默失败
    } finally {
      set(s => ({ loading: { ...s.loading, monthlyCost: false } }));
    }
  },

  fetchBudget: async () => {
    set(s => ({ loading: { ...s.loading, budget: true } }));
    try {
      const data = await costApi.getBudget();
      set({ budget: data });
    } catch (e) {
      // 静默失败
    } finally {
      set(s => ({ loading: { ...s.loading, budget: false } }));
    }
  },

  setBudget: async (monthlyLimit: number) => {
    try {
      await costApi.setBudget(monthlyLimit);
      // 刷新预算状态
      await get().fetchBudget();
    } catch (e) {
      throw e;
    }
  },

  switchModel: async (model: string) => {
    set(s => ({ loading: { ...s.loading, switching: true } }));
    try {
      await costApi.switchModel(model);
      await get().fetchCurrentModel();
    } catch (e) {
      throw e;
    } finally {
      set(s => ({ loading: { ...s.loading, switching: false } }));
    }
  },
}));

export default useCostStore;

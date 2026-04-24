import api from './index';

export interface ModelInfo {
  name: string;
  description: string;
  input_price_per_1k: number;
  output_price_per_1k: number;
  input_price_per_1m: number;
  output_price_per_1m: number;
}

export interface SessionCost {
  session_id: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost: number;
  call_count: number;
}

export interface DailyCost {
  date: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost: number;
  call_count: number;
}

export interface DailyBreakdown {
  date: string;
  cost: number;
  calls: number;
}

export interface MonthlyCost {
  year: number;
  month: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  total_cost: number;
  call_count: number;
  daily_breakdown: DailyBreakdown[];
}

export interface BudgetStatus {
  monthly_limit: number;
  used: number;
  remaining: number;
  percent: number;
  over_budget: boolean;
}

export interface CurrentModel {
  model: string;
  description: string;
  input_price_per_1k: number;
  output_price_per_1k: number;
}

export const costApi = {
  /** 获取可用模型列表 */
  getModels: () =>
    api.get<{ models: ModelInfo[] }>('/cost/models').then(r => r.data),

  /** 获取会话费用 */
  getSessionCost: (sessionId: string) =>
    api.get<SessionCost>(`/cost/session/${sessionId}`).then(r => r.data),

  /** 获取日费用（默认今天） */
  getDailyCost: (date?: string) =>
    api.get<DailyCost>('/cost/daily', { params: date ? { date } : {} }).then(r => r.data),

  /** 获取月费用 */
  getMonthlyCost: (year?: number, month?: number) =>
    api
      .get<MonthlyCost>('/cost/monthly', { params: { year, month } })
      .then(r => r.data),

  /** 获取预算状态 */
  getBudget: () =>
    api.get<BudgetStatus>('/cost/budget').then(r => r.data),

  /** 设置月度预算 */
  setBudget: (monthlyLimit: number) =>
    api.put('/cost/budget', { monthly_limit: monthlyLimit }).then(r => r.data),

  /** 获取当前模型 */
  getCurrentModel: () =>
    api.get<CurrentModel>('/cost/current-model').then(r => r.data),

  /** 切换模型 */
  switchModel: (model: string) =>
    api.put('/cost/current-model', { model }).then(r => r.data),
};

export default costApi;

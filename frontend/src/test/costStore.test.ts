/**
 * costStore.test.ts
 *
 * 测试：
 * - fetchModels：成功更新 models / 失败静默处理
 * - fetchSessionCost：成功更新 sessionCost / 空 sessionId 不发请求
 * - fetchMonthlyCost：成功更新 monthlyCost
 * - setBudget：调用 API 后刷新预算状态
 * - switchModel：调用 API 后刷新当前模型
 * - 加载状态流转（loading flags）
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

// ── mock costApi ─────────────────────────────────────────────────────────────

vi.mock('../api/costApi', () => ({
  default: {
    getModels: vi.fn(),
    getCurrentModel: vi.fn(),
    getSessionCost: vi.fn(),
    getMonthlyCost: vi.fn(),
    getBudget: vi.fn(),
    setBudget: vi.fn(),
    switchModel: vi.fn(),
  },
  costApi: {
    getModels: vi.fn(),
    getCurrentModel: vi.fn(),
    getSessionCost: vi.fn(),
    getMonthlyCost: vi.fn(),
    getBudget: vi.fn(),
    setBudget: vi.fn(),
    switchModel: vi.fn(),
  },
}))

import costApi from '../api/costApi'
import { useCostStore } from '../stores/costStore'


// ── helpers ───────────────────────────────────────────────────────────────────

function resetStore() {
  // 直接设置初始状态
  useCostStore.setState({
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
  })
}

const mockModels = {
  models: [
    {
      name: 'deepseek-chat',
      description: 'DeepSeek-V3',
      input_price_per_1k: 0.00027,
      output_price_per_1k: 0.00110,
      input_price_per_1m: 0.27,
      output_price_per_1m: 1.10,
    },
  ],
}

const mockSessionCost = {
  session_id: 'sess-001',
  total_input_tokens: 500,
  total_output_tokens: 300,
  total_tokens: 800,
  total_cost: 0.000485,
  call_count: 3,
}

const mockMonthlyCost = {
  year: 2026,
  month: 4,
  total_input_tokens: 10000,
  total_output_tokens: 5000,
  total_tokens: 15000,
  total_cost: 0.0082,
  call_count: 30,
  daily_breakdown: [],
}

const mockBudget = {
  monthly_limit: 10.0,
  used: 0.0082,
  remaining: 9.9918,
  percent: 0.1,
  over_budget: false,
}

const mockCurrentModel = {
  model: 'deepseek-chat',
  description: 'DeepSeek-V3（通用对话）',
  input_price_per_1k: 0.00027,
  output_price_per_1k: 0.00110,
}


// ══════════════════════════════════════════════════════════════════════════════
// fetchModels
// ══════════════════════════════════════════════════════════════════════════════

describe('costStore.fetchModels', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
  })

  it('成功后 models 状态更新', async () => {
    vi.mocked(costApi.getModels).mockResolvedValueOnce(mockModels as any)
    await useCostStore.getState().fetchModels()
    expect(useCostStore.getState().models).toHaveLength(1)
    expect(useCostStore.getState().models[0].name).toBe('deepseek-chat')
  })

  it('加载完成后 loading.models 恢复为 false', async () => {
    vi.mocked(costApi.getModels).mockResolvedValueOnce(mockModels as any)
    await useCostStore.getState().fetchModels()
    expect(useCostStore.getState().loading.models).toBe(false)
  })

  it('API 失败时 models 保持原有状态（静默失败）', async () => {
    vi.mocked(costApi.getModels).mockRejectedValueOnce(new Error('network error'))
    await useCostStore.getState().fetchModels()
    expect(useCostStore.getState().models).toEqual([])
    expect(useCostStore.getState().loading.models).toBe(false)
  })
})


// ══════════════════════════════════════════════════════════════════════════════
// fetchSessionCost
// ══════════════════════════════════════════════════════════════════════════════

describe('costStore.fetchSessionCost', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
  })

  it('空 sessionId 时不调用 API', async () => {
    await useCostStore.getState().fetchSessionCost('')
    expect(costApi.getSessionCost).not.toHaveBeenCalled()
  })

  it('成功后 sessionCost 更新', async () => {
    vi.mocked(costApi.getSessionCost).mockResolvedValueOnce(mockSessionCost as any)
    await useCostStore.getState().fetchSessionCost('sess-001')
    const state = useCostStore.getState()
    expect(state.sessionCost).not.toBeNull()
    expect(state.sessionCost?.session_id).toBe('sess-001')
    expect(state.sessionCost?.total_tokens).toBe(800)
  })

  it('loading.sessionCost 在请求完成后恢复为 false', async () => {
    vi.mocked(costApi.getSessionCost).mockResolvedValueOnce(mockSessionCost as any)
    await useCostStore.getState().fetchSessionCost('sess-001')
    expect(useCostStore.getState().loading.sessionCost).toBe(false)
  })

  it('API 失败时静默处理，loading 恢复', async () => {
    vi.mocked(costApi.getSessionCost).mockRejectedValueOnce(new Error('404'))
    await useCostStore.getState().fetchSessionCost('sess-bad')
    expect(useCostStore.getState().sessionCost).toBeNull()
    expect(useCostStore.getState().loading.sessionCost).toBe(false)
  })
})


// ══════════════════════════════════════════════════════════════════════════════
// fetchMonthlyCost
// ══════════════════════════════════════════════════════════════════════════════

describe('costStore.fetchMonthlyCost', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
  })

  it('成功后 monthlyCost 更新', async () => {
    vi.mocked(costApi.getMonthlyCost).mockResolvedValueOnce(mockMonthlyCost as any)
    await useCostStore.getState().fetchMonthlyCost(2026, 4)
    const state = useCostStore.getState()
    expect(state.monthlyCost?.year).toBe(2026)
    expect(state.monthlyCost?.month).toBe(4)
  })

  it('API 失败时静默处理', async () => {
    vi.mocked(costApi.getMonthlyCost).mockRejectedValueOnce(new Error('500'))
    await useCostStore.getState().fetchMonthlyCost()
    expect(useCostStore.getState().monthlyCost).toBeNull()
  })
})


// ══════════════════════════════════════════════════════════════════════════════
// setBudget
// ══════════════════════════════════════════════════════════════════════════════

describe('costStore.setBudget', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
  })

  it('调用 setBudget API 并刷新预算状态', async () => {
    vi.mocked(costApi.setBudget).mockResolvedValueOnce({} as any)
    vi.mocked(costApi.getBudget).mockResolvedValueOnce(mockBudget as any)

    await useCostStore.getState().setBudget(10.0)

    expect(costApi.setBudget).toHaveBeenCalledWith(10.0)
    expect(costApi.getBudget).toHaveBeenCalled()
    expect(useCostStore.getState().budget?.monthly_limit).toBe(10.0)
  })

  it('API 失败时向上抛出异常', async () => {
    vi.mocked(costApi.setBudget).mockRejectedValueOnce(new Error('budget error'))
    await expect(useCostStore.getState().setBudget(5.0)).rejects.toThrow('budget error')
  })
})


// ══════════════════════════════════════════════════════════════════════════════
// switchModel
// ══════════════════════════════════════════════════════════════════════════════

describe('costStore.switchModel', () => {
  beforeEach(() => {
    resetStore()
    vi.clearAllMocks()
  })

  it('switchModel 调用 API 并刷新当前模型', async () => {
    vi.mocked(costApi.switchModel).mockResolvedValueOnce({} as any)
    vi.mocked(costApi.getCurrentModel).mockResolvedValueOnce(mockCurrentModel as any)

    await useCostStore.getState().switchModel('deepseek-chat')

    expect(costApi.switchModel).toHaveBeenCalledWith('deepseek-chat')
    expect(costApi.getCurrentModel).toHaveBeenCalled()
    expect(useCostStore.getState().currentModel?.model).toBe('deepseek-chat')
  })

  it('loading.switching 在切换完成后恢复为 false', async () => {
    vi.mocked(costApi.switchModel).mockResolvedValueOnce({} as any)
    vi.mocked(costApi.getCurrentModel).mockResolvedValueOnce(mockCurrentModel as any)

    await useCostStore.getState().switchModel('deepseek-chat')
    expect(useCostStore.getState().loading.switching).toBe(false)
  })

  it('API 失败时向上抛出异常，loading 恢复', async () => {
    vi.mocked(costApi.switchModel).mockRejectedValueOnce(new Error('switch error'))
    await expect(useCostStore.getState().switchModel('deepseek-reasoner')).rejects.toThrow()
    expect(useCostStore.getState().loading.switching).toBe(false)
  })
})

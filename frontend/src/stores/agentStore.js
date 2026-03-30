import { create } from 'zustand';

/**
 * Agent 状态管理 Store
 * 
 * 用于管理 Agent 模式的执行状态：
 * - 意图识别结果
 * - 任务计划
 * - 执行步骤进度
 * - 最终结果
 */
const useAgentStore = create((set, get) => ({
    // ============ 状态 ============
    
    /** 是否处于 Agent 模式 */
    isAgentMode: false,
    
    /** 是否正在处理中 */
    isProcessing: false,
    
    /** 意图识别结果 */
    intent: null,
    
    /** 任务计划列表 */
    plan: [],
    
    /** 当前执行步骤（从1开始） */
    currentStep: 0,
    
    /** 步骤执行结果映射 { stepNum: result } */
    stepResults: {},
    
    /** 最终答案 */
    finalAnswer: '',
    
    /** 是否已完成 */
    isComplete: false,
    
    /** 错误信息 */
    error: null,
    
    // ============ Actions ============
    
    /** 开始 Agent 模式 */
    startAgentMode: () => set({
        isAgentMode: true,
        isProcessing: true,
        isComplete: false,
        error: null,
        intent: null,
        plan: [],
        currentStep: 0,
        stepResults: {},
        finalAnswer: ''
    }),
    
    /** 退出 Agent 模式 */
    exitAgentMode: () => set({
        isAgentMode: false,
        isProcessing: false
    }),
    
    /** 设置意图识别结果 */
    setIntent: (intent) => set({ intent }),
    
    /** 设置任务计划 */
    setPlan: (plan) => set({ plan }),
    
    /** 更新步骤状态（步骤开始时调用） */
    startStep: (step) => set(state => ({
        currentStep: step
    })),
    
    /** 更新步骤结果 */
    updateStepResult: (step, result) => set(state => ({
        stepResults: { ...state.stepResults, [step]: result }
    })),
    
    /** 追加最终答案内容 */
    appendAnswer: (chunk) => set(state => ({
        finalAnswer: state.finalAnswer + chunk
    })),
    
    /** 设置最终答案（完整替换） */
    setFinalAnswer: (answer) => set({
        finalAnswer: answer
    }),
    
    /** 标记完成 */
    markComplete: () => set({
        isProcessing: false,
        isComplete: true
    }),
    
    /** 设置错误 */
    setError: (error) => set({
        error,
        isProcessing: false
    }),
    
    /** 重置所有状态 */
    reset: () => set({
        isAgentMode: false,
        isProcessing: false,
        intent: null,
        plan: [],
        currentStep: 0,
        stepResults: {},
        finalAnswer: '',
        isComplete: false,
        error: null
    }),
    
    /** 获取步骤状态 */
    getStepStatus: (stepNum) => {
        const state = get();
        if (stepNum < state.currentStep) return 'completed';
        if (stepNum === state.currentStep) return 'running';
        return 'pending';
    },
    
    /** 获取当前步骤描述 */
    getCurrentStepDescription: () => {
        const state = get();
        if (state.currentStep === 0) return null;
        const step = state.plan.find(p => p.step === state.currentStep);
        return step?.description || `步骤 ${state.currentStep}`;
    }
}));

export default useAgentStore;

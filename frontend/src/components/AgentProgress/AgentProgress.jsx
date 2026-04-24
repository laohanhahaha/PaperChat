/**
 * [DEPRECATED] 此组件已被 props 驱动版替代，保留仅为过渡期参考。
 * 替代组件: frontend/src/components/ChatPage/AgentProgress.jsx（props 驱动版，当前正在使用）
 * 请勿在新代码中导入此组件。
 */
import React from 'react';
import useAgentStore from '../../stores/agentStore';
import styles from './AgentProgress.module.css';

/**
 * Agent 执行进度组件
 * 
 * 展示 Agent 执行进度：
 * - 意图识别结果（小标签）
 * - 任务步骤列表（步骤编号 + 描述 + 状态图标）
 * - 当前执行步骤高亮
 * - 已完成步骤打勾
 * - 最终答案区域
 */
const AgentProgress = () => {
    const {
        isAgentMode,
        isProcessing,
        intent,
        plan,
        currentStep,
        stepResults,
        finalAnswer,
        isComplete,
        error
    } = useAgentStore();

    // 如果不是 Agent 模式，不渲染
    if (!isAgentMode) {
        return null;
    }

    // 获取意图类型显示文本
    const getIntentLabel = (intentType) => {
        const labels = {
            simple_qa: '简单问答',
            analysis: '分析请求',
            comparison: '对比分析',
            search: '信息搜索',
            writing: '内容生成',
            multi_step: '复杂任务'
        };
        return labels[intentType] || intentType;
    };

    // 获取复杂度显示文本
    const getComplexityLabel = (complexity) => {
        const labels = {
            low: '低',
            medium: '中',
            high: '高'
        };
        return labels[complexity] || complexity;
    };

    // 获取复杂度样式类
    const getComplexityClass = (complexity) => {
        const classes = {
            low: styles.complexityLow,
            medium: styles.complexityMedium,
            high: styles.complexityHigh
        };
        return classes[complexity] || '';
    };

    // 获取步骤状态图标
    const getStepIcon = (stepNum) => {
        if (stepNum < currentStep) {
            // 已完成
            return (
                <svg className={styles.iconCompleted} viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
            );
        }
        if (stepNum === currentStep && isProcessing) {
            // 进行中
            return (
                <div className={styles.spinner}>
                    <div className={styles.spinnerInner}></div>
                </div>
            );
        }
        // 待处理
        return (
            <div className={styles.iconPending}>
                <span>{stepNum}</span>
            </div>
        );
    };

    // 获取步骤状态样式类
    const getStepClass = (stepNum) => {
        if (stepNum < currentStep) return styles.stepCompleted;
        if (stepNum === currentStep && isProcessing) return styles.stepRunning;
        return styles.stepPending;
    };

    return (
        <div className={styles.container}>
            {/* 头部：意图识别结果 */}
            {intent && (
                <div className={styles.intentSection}>
                    <div className={styles.intentHeader}>
                        <span className={styles.intentLabel}>意图识别</span>
                        <span className={`${styles.complexityBadge} ${getComplexityClass(intent.complexity)}`}>
                            复杂度: {getComplexityLabel(intent.complexity)}
                        </span>
                    </div>
                    <div className={styles.intentType}>
                        {getIntentLabel(intent.intent)}
                    </div>
                    {intent.reasoning && (
                        <div className={styles.intentReasoning}>
                            {intent.reasoning}
                        </div>
                    )}
                </div>
            )}

            {/* 任务步骤列表 */}
            {plan.length > 0 && (
                <div className={styles.planSection}>
                    <div className={styles.sectionTitle}>执行计划</div>
                    <div className={styles.stepsList}>
                        {plan.map((step) => (
                            <div
                                key={step.step}
                                className={`${styles.stepItem} ${getStepClass(step.step)}`}
                            >
                                <div className={styles.stepIcon}>
                                    {getStepIcon(step.step)}
                                </div>
                                <div className={styles.stepContent}>
                                    <div className={styles.stepHeader}>
                                        <span className={styles.stepNumber}>步骤 {step.step}</span>
                                        <span className={styles.stepTool}>{step.tool}</span>
                                    </div>
                                    <div className={styles.stepDescription}>
                                        {step.description}
                                    </div>
                                    {/* 显示步骤结果（如果已完成） */}
                                    {step.step < currentStep && stepResults[step.step] && (
                                        <div className={styles.stepResult}>
                                            {stepResults[step.step].summary && (
                                                <span className={styles.resultTag}>
                                                    已生成摘要
                                                </span>
                                            )}
                                            {stepResults[step.step].results && (
                                                <span className={styles.resultTag}>
                                                    检索到 {stepResults[step.step].results.length || stepResults[step.step].count || 0} 条结果
                                                </span>
                                            )}
                                            {stepResults[step.step].points && (
                                                <span className={styles.resultTag}>
                                                    提取了 {stepResults[step.step].points.length || stepResults[step.step].count || 0} 个知识点
                                                </span>
                                            )}
                                            {stepResults[step.step].translation && (
                                                <span className={styles.resultTag}>
                                                    翻译完成
                                                </span>
                                            )}
                                            {stepResults[step.step].explanation && (
                                                <span className={styles.resultTag}>
                                                    解释完成
                                                </span>
                                            )}
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* 最终答案区域 */}
            {(finalAnswer || isProcessing) && (
                <div className={styles.answerSection}>
                    <div className={styles.sectionTitle}>
                        {isComplete ? '最终答案' : '生成回答中...'}
                    </div>
                    <div className={`${styles.answerContent} ${isProcessing && !finalAnswer ? styles.answerLoading : ''}`}>
                        {finalAnswer ? (
                            <div className={styles.answerText}>{finalAnswer}</div>
                        ) : (
                            <div className={styles.loadingDots}>
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>
                        )}
                        {isProcessing && finalAnswer && (
                            <span className={styles.cursor}>▋</span>
                        )}
                    </div>
                </div>
            )}

            {/* 错误提示 */}
            {error && (
                <div className={styles.errorSection}>
                    <div className={styles.errorTitle}>执行出错</div>
                    <div className={styles.errorMessage}>{error}</div>
                </div>
            )}
        </div>
    );
};

export default AgentProgress;

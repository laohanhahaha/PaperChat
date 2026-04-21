/**
 * AgentProgress - 展示 ReAct Agent 的 Thought/Action/Observation 过程
 * 
 * 类似 ThinkingBlock 的折叠式 UI，但展示多步推理过程
 */
import React, { useState, useEffect } from 'react';
import styles from './AgentProgress.module.css';

// 辅助函数：解析研究阶段
function parseResearchPhase(content) {
  if (content.startsWith('[检索阶段]')) return { phase: 'search', label: '检索阶段', content: content.slice(6) };
  if (content.startsWith('[分析阶段]')) return { phase: 'analyze', label: '分析阶段', content: content.slice(6) };
  if (content.startsWith('[推荐阶段]')) return { phase: 'recommend', label: '推荐阶段', content: content.slice(6) };
  return null;
}

// SVG Icons
const SearchIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="11" cy="11" r="8"></circle>
    <path d="m21 21-4.3-4.3"></path>
  </svg>
);

const AnalyzeIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 3v18h18"></path>
    <path d="M18 17V9"></path>
    <path d="M13 17V5"></path>
    <path d="M8 17v-3"></path>
  </svg>
);

const RecommendIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"></path>
    <path d="M9 18h6"></path>
    <path d="M10 22h4"></path>
  </svg>
);

const ReflectionIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M1 4v6h6" />
    <path d="M23 20v-6h-6" />
    <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15" />
  </svg>
);

const AgentProgress = ({ steps = [], isRunning = false }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  
  // Agent 运行中自动展开，结束后可折叠
  useEffect(() => {
    if (isRunning) setIsExpanded(true);
  }, [isRunning]);

  if (!steps || steps.length === 0) return null;

  const totalSteps = Math.max(...steps.map(s => s.step || 0));

  return (
    <div className={styles.agentProgress}>
      <div 
        className={styles.header} 
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className={`${styles.indicator} ${isRunning ? styles.running : styles.done}`}>
          {isRunning ? '⚙️' : '✅'}
        </span>
        <span className={styles.title}>
          {isRunning 
            ? `Agent 推理中... (${totalSteps} 步)` 
            : `Agent 推理完成 (${totalSteps} 步)`
          }
        </span>
        <span className={`${styles.chevron} ${isExpanded ? styles.expanded : ''}`}>
          ▾
        </span>
      </div>
      
      {isExpanded && (
        <div className={styles.stepsContainer}>
          {steps.map((step, idx) => {
            const prevStep = idx > 0 ? steps[idx - 1] : null;
            const showDivider = prevStep && 
              prevStep.type === 'agent_thought' && 
              step.type === 'agent_thought' &&
              parseResearchPhase(prevStep.content)?.phase !== parseResearchPhase(step.content)?.phase &&
              parseResearchPhase(step.content) !== null;
            
            return (
              <React.Fragment key={idx}>
                {showDivider && (
                  <div className={styles.phaseDivider}>
                    <span className={styles.phaseDividerText}>
                      切换到 {parseResearchPhase(step.content)?.label}
                    </span>
                  </div>
                )}
                <StepItem step={step} />
              </React.Fragment>
            );
          })}
          {isRunning && (
            <div className={styles.thinkingCursor}>
              <span className={styles.dot}>●</span>
              <span className={styles.dot}>●</span>
              <span className={styles.dot}>●</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

const StepItem = ({ step }) => {
  switch (step.type) {
    case 'agent_thought': {
      const phaseInfo = parseResearchPhase(step.content);
      
      if (phaseInfo) {
        // 深度研究模式 - 显示角色 badge
        const badgeClass = {
          search: styles.phaseBadgeSearch,
          analyze: styles.phaseBadgeAnalyze,
          recommend: styles.phaseBadgeRecommend
        }[phaseInfo.phase];
        
        const Icon = {
          search: SearchIcon,
          analyze: AnalyzeIcon,
          recommend: RecommendIcon
        }[phaseInfo.phase];
        
        return (
          <div className={styles.stepItem}>
            <span className={`${styles.stepBadge} ${styles.thoughtBadge}`}>💭 思考</span>
            <span className={styles.stepContent}>
              <span className={`${styles.phaseBadge} ${badgeClass}`}>
                <Icon />
                {phaseInfo.label}
              </span>
              {phaseInfo.content}
            </span>
          </div>
        );
      }
      
      // 普通模式 - 保持原样
      return (
        <div className={styles.stepItem}>
          <span className={`${styles.stepBadge} ${styles.thoughtBadge}`}>💭 思考</span>
          <span className={styles.stepContent}>{step.content}</span>
        </div>
      );
    }
    case 'agent_action':
      return (
        <div className={styles.stepItem}>
          <span className={`${styles.stepBadge} ${styles.actionBadge}`}>🔧 {step.tool}</span>
          <span className={styles.stepContent}>
            {typeof step.input === 'object' ? JSON.stringify(step.input, null, 0) : step.input}
          </span>
        </div>
      );
    case 'reflection':
      return (
        <div className={`${styles.stepItem} ${styles.stepReflection}`}>
          <span className={`${styles.stepBadge} ${styles.reflectionBadge}`}>
            <ReflectionIcon />
            反思
          </span>
          <span className={styles.stepContent}>{step.content}</span>
        </div>
      );
    case 'agent_observation':
      return (
        <div className={styles.stepItem}>
          <span className={`${styles.stepBadge} ${styles.observationBadge}`}>👁 观察</span>
          <span className={styles.stepContent}>
            {step.content?.length > 200 ? step.content.slice(0, 200) + '...' : step.content}
          </span>
        </div>
      );
    default:
      return null;
  }
};

export default React.memo(AgentProgress);

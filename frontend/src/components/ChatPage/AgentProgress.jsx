/**
 * AgentProgress - 展示 ReAct Agent 的 Thought/Action/Observation 过程
 * 
 * 支持两种模式：
 * 1. 单 Agent 模式（无 subAgent 字段）：保持原有扁平列表展示
 * 2. 多 Agent 模式（有 subAgent 字段）：按子 Agent 分组，层级展示
 */
import React, { useState, useEffect, useMemo } from 'react';
import styles from './AgentProgress.module.css';

// 根据名称智能匹配图标的函数（替代硬编码 ROLE_CONFIG）
function getAgentConfig(agentKey) {
  // 预置角色
  if (agentKey === 'orchestrator') return { icon: '🧠', label: '协调器' };

  // 根据名称关键词智能匹配图标
  const name = agentKey.toLowerCase();
  if (name.includes('检索') || name.includes('search') || name.includes('retriev'))
    return { icon: '🔍', label: agentKey };
  if (name.includes('分析') || name.includes('analyz') || name.includes('evaluat'))
    return { icon: '📊', label: agentKey };
  if (name.includes('推荐') || name.includes('recommend') || name.includes('suggest'))
    return { icon: '💡', label: agentKey };
  if (name.includes('综述') || name.includes('review') || name.includes('survey'))
    return { icon: '📝', label: agentKey };
  if (name.includes('对比') || name.includes('compar'))
    return { icon: '⚖️', label: agentKey };
  if (name.includes('写作') || name.includes('writ'))
    return { icon: '✍️', label: agentKey };
  if (name.includes('翻译') || name.includes('translat'))
    return { icon: '🌐', label: agentKey };
  if (name.includes('数据') || name.includes('data') || name.includes('统计'))
    return { icon: '📈', label: agentKey };
  if (name.includes('方法') || name.includes('method'))
    return { icon: '🧪', label: agentKey };

  // 默认
  return { icon: '🤖', label: agentKey };
}

// 辅助函数：解析研究阶段
function parseResearchPhase(content) {
  if (!content) return null;
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

// ─── 单步渲染 ────────────────────────────────────────────────
const StepItem = ({ step }) => {
  switch (step.type) {
    case 'agent_thought': {
      const phaseInfo = parseResearchPhase(step.content);
      if (phaseInfo) {
        const badgeClass = {
          search: styles.phaseBadgeSearch,
          analyze: styles.phaseBadgeAnalyze,
          recommend: styles.phaseBadgeRecommend
        }[phaseInfo.phase];
        const Icon = { search: SearchIcon, analyze: AnalyzeIcon, recommend: RecommendIcon }[phaseInfo.phase];
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

// ─── 子 Agent 分组块 ─────────────────────────────────────────
const SubAgentBlock = ({ agentKey, steps, isRunning, isLast }) => {
  const config = getAgentConfig(agentKey);
  // 运行中最后一个 agent 默认展开，其余完成后折叠
  const [expanded, setExpanded] = useState(true);

  // 当前 agent 如果还在运行（isRunning && isLast），自动保持展开
  useEffect(() => {
    if (isRunning && isLast) setExpanded(true);
  }, [isRunning, isLast]);

  // 生成摘要：取最后一条 observation / thought 内容
  const summary = useMemo(() => {
    const obs = [...steps].reverse().find(s => s.type === 'agent_observation' || s.type === 'agent_thought');
    if (!obs) return null;
    const text = obs.content || '';
    return text.length > 60 ? text.slice(0, 60) + '…' : text;
  }, [steps]);

  const isDone = !isRunning || !isLast;

  return (
    <div className={styles.subAgentBlock}>
      <div
        className={`${styles.subAgentHeader} ${isDone ? styles.subAgentDone : styles.subAgentRunning}`}
        onClick={() => setExpanded(v => !v)}
        role="button"
        tabIndex={0}
        onKeyDown={e => e.key === 'Enter' && setExpanded(v => !v)}
      >
        <span className={styles.subAgentIcon}>{config.icon}</span>
        <span className={styles.subAgentLabel}>{config.label}</span>
        {isRunning && isLast && (
          <span className={styles.subAgentSpinner} />
        )}
        {isDone && !expanded && summary && (
          <span className={styles.subAgentSummary}>{summary}</span>
        )}
        <span className={`${styles.chevron} ${expanded ? styles.expanded : ''}`}>▾</span>
      </div>

      {expanded && (
        <div className={styles.subAgentSteps}>
          {steps.map((step, idx) => (
            <div key={idx} className={styles.subAgentStepRow}>
              <span className={styles.subAgentTreeLine}>└─</span>
              <StepItem step={step} />
            </div>
          ))}
          {isRunning && isLast && (
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

// ─── 主组件 ──────────────────────────────────────────────────
const AgentProgress = ({ steps = [], isRunning = false }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  useEffect(() => {
    if (isRunning) setIsExpanded(true);
  }, [isRunning]);

  if (!steps || steps.length === 0) return null;

  // 判断是否是多 Agent 模式
  const hasSubAgent = steps.some(s => s.subAgent);

  if (hasSubAgent) {
    // ── 多 Agent 分组模式 ──
    // 按出现顺序收集各 agent 的 steps，保持顺序
    const agentOrder = [];
    const agentMap = {};
    for (const step of steps) {
      const key = step.subAgent || 'unknown';
      if (!agentMap[key]) {
        agentMap[key] = [];
        agentOrder.push(key);
      }
      agentMap[key].push(step);
    }

    const totalAgents = agentOrder.length;

    // 生成专家标签列表（排除 orchestrator / unknown）
    const expertLabels = agentOrder
      .filter(k => k !== 'orchestrator' && k !== 'unknown')
      .map(k => getAgentConfig(k).label);

    // 运行中：找到当前活跃的子 Agent（最后一个）
    const currentAgentKey = isRunning ? agentOrder[agentOrder.length - 1] : null;
    const currentAgentLabel = currentAgentKey
      ? getAgentConfig(currentAgentKey).label
      : null;

    // 标题文案
    const headerTitle = isRunning
      ? `多Agent 协作中${currentAgentLabel ? ` — ${currentAgentLabel} 运行中` : ''}...`
      : expertLabels.length > 0
        ? `多Agent 研究完成 (${expertLabels.join(' + ')})`
        : `多Agent 协作完成 (${totalAgents} 个专家)`;

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
            {headerTitle}
          </span>
          <span className={`${styles.chevron} ${isExpanded ? styles.expanded : ''}`}>▾</span>
        </div>

        {isExpanded && (
          <div className={styles.stepsContainer}>
            {agentOrder.map((agentKey, idx) => (
              <SubAgentBlock
                key={agentKey}
                agentKey={agentKey}
                steps={agentMap[agentKey]}
                isRunning={isRunning}
                isLast={idx === agentOrder.length - 1}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  // ── 单 Agent 原有模式（向后兼容）──
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

export default React.memo(AgentProgress);

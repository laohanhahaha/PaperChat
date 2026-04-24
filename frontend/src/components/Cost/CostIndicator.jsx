import React, { useEffect, useState } from 'react';
import { useCostStore } from '../../stores/costStore';
import styles from './CostIndicator.module.css';

/**
 * 轻量级实时成本指示器
 * 显示当前会话消耗的 token 数和费用，可折叠/展开
 */
export default function CostIndicator({ sessionId }) {
  const { sessionCost, fetchSessionCost, currentModel } = useCostStore();
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!sessionId) return;
    fetchSessionCost(sessionId);
    // 每 30s 刷新一次
    const timer = setInterval(() => fetchSessionCost(sessionId), 30000);
    return () => clearInterval(timer);
  }, [sessionId, fetchSessionCost]);

  if (!sessionCost || sessionCost.call_count === 0) return null;

  const cost = sessionCost.total_cost;
  const tokens = sessionCost.total_tokens;
  const costStr = cost < 0.0001 ? '<$0.0001' : `$${cost.toFixed(4)}`;

  return (
    <div className={`${styles.wrapper} ${expanded ? styles.expanded : ''}`}>
      <button
        className={styles.toggle}
        onClick={() => setExpanded(v => !v)}
        title={expanded ? '收起费用详情' : '查看费用详情'}
      >
        <span className={styles.coinIcon}>💰</span>
        <span className={styles.costBadge}>{costStr}</span>
        <span className={styles.chevron}>{expanded ? '▲' : '▼'}</span>
      </button>

      {expanded && (
        <div className={styles.detail}>
          <div className={styles.row}>
            <span className={styles.rowLabel}>本次对话费用</span>
            <span className={styles.rowValue}>{costStr}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.rowLabel}>总 Token 数</span>
            <span className={styles.rowValue}>{tokens.toLocaleString()}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.rowLabel}>输入 / 输出</span>
            <span className={styles.rowValue}>
              {sessionCost.total_input_tokens.toLocaleString()} / {sessionCost.total_output_tokens.toLocaleString()}
            </span>
          </div>
          <div className={styles.row}>
            <span className={styles.rowLabel}>调用次数</span>
            <span className={styles.rowValue}>{sessionCost.call_count}</span>
          </div>
          {currentModel && (
            <div className={styles.row}>
              <span className={styles.rowLabel}>当前模型</span>
              <span className={styles.rowValue}>{currentModel.model.replace('deepseek-', '')}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

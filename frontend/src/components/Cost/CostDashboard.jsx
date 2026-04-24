import React, { useEffect, useState } from 'react';
import { useCostStore } from '../../stores/costStore';
import styles from './CostDashboard.module.css';

/**
 * 月度费用概览面板
 * - 预算进度条（已用/预算）
 * - 月度总费用 + Token 统计
 * - 每日费用柱状图（纯 CSS）
 * - 设置预算输入框
 */
export default function CostDashboard({ onClose }) {
  const {
    monthlyCost,
    budget,
    fetchMonthlyCost,
    fetchBudget,
    setBudget,
    loading,
  } = useCostStore();

  const [budgetInput, setBudgetInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');

  useEffect(() => {
    fetchMonthlyCost();
    fetchBudget();
  }, [fetchMonthlyCost, fetchBudget]);

  useEffect(() => {
    if (budget) setBudgetInput(String(budget.monthly_limit));
  }, [budget]);

  const handleSaveBudget = async () => {
    const val = parseFloat(budgetInput);
    if (isNaN(val) || val <= 0) { setSaveMsg('请输入有效金额'); return; }
    setSaving(true);
    try {
      await setBudget(val);
      setSaveMsg('✓ 已保存');
      setTimeout(() => setSaveMsg(''), 2000);
    } catch {
      setSaveMsg('保存失败');
    } finally {
      setSaving(false);
    }
  };

  const budgetPercent = budget?.percent ?? 0;
  const budgetColor = budgetPercent >= 90 ? '#ef4444' : budgetPercent >= 70 ? '#f59e0b' : '#10b981';

  // 计算柱状图最大值（至少 $0.001 避免除零）
  const dailyData = monthlyCost?.daily_breakdown ?? [];
  const maxDailyCost = Math.max(...dailyData.map(d => d.cost), 0.001);

  return (
    <div className={styles.panel}>
      <div className={styles.header}>
        <h3 className={styles.title}>费用面板</h3>
        {onClose && (
          <button className={styles.closeBtn} onClick={onClose}>✕</button>
        )}
      </div>

      {/* 预算状态 */}
      {budget && (
        <div className={styles.section}>
          <div className={styles.sectionTitle}>本月预算</div>
          <div className={styles.budgetRow}>
            <span className={styles.budgetUsed}>${budget.used.toFixed(4)}</span>
            <span className={styles.budgetSep}>/</span>
            <span className={styles.budgetLimit}>${budget.monthly_limit.toFixed(2)}</span>
            <span className={`${styles.budgetPercent} ${budget.over_budget ? styles.overBudget : ''}`}>
              {budgetPercent}%
            </span>
          </div>
          <div className={styles.progressBar}>
            <div
              className={styles.progressFill}
              style={{ width: `${Math.min(budgetPercent, 100)}%`, background: budgetColor }}
            />
          </div>
          {budget.over_budget && (
            <div className={styles.overBudgetWarning}>⚠️ 已超出本月预算！</div>
          )}
        </div>
      )}

      {/* 月度统计 */}
      {monthlyCost && (
        <div className={styles.section}>
          <div className={styles.sectionTitle}>
            {monthlyCost.year}年{monthlyCost.month}月统计
          </div>
          <div className={styles.statsGrid}>
            <div className={styles.statItem}>
              <div className={styles.statValue}>${monthlyCost.total_cost.toFixed(4)}</div>
              <div className={styles.statLabel}>总费用</div>
            </div>
            <div className={styles.statItem}>
              <div className={styles.statValue}>{monthlyCost.total_tokens.toLocaleString()}</div>
              <div className={styles.statLabel}>总 Token</div>
            </div>
            <div className={styles.statItem}>
              <div className={styles.statValue}>{monthlyCost.call_count}</div>
              <div className={styles.statLabel}>调用次数</div>
            </div>
          </div>
        </div>
      )}

      {/* 每日费用柱状图 */}
      {dailyData.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionTitle}>每日费用趋势</div>
          <div className={styles.barChart}>
            {dailyData.map(d => {
              const heightPct = (d.cost / maxDailyCost) * 100;
              const day = d.date.slice(-2);
              return (
                <div key={d.date} className={styles.barGroup} title={`${d.date}: $${d.cost.toFixed(4)}，${d.calls}次`}>
                  <div className={styles.barTrack}>
                    <div
                      className={styles.barFill}
                      style={{ height: `${heightPct}%` }}
                    />
                  </div>
                  <div className={styles.barLabel}>{day}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 设置预算 */}
      <div className={styles.section}>
        <div className={styles.sectionTitle}>设置月预算（美元）</div>
        <div className={styles.budgetForm}>
          <span className={styles.dollarSign}>$</span>
          <input
            type="number"
            className={styles.budgetInput}
            value={budgetInput}
            onChange={e => setBudgetInput(e.target.value)}
            min="0.01"
            step="0.5"
            placeholder="10.00"
          />
          <button
            className={styles.saveBtn}
            onClick={handleSaveBudget}
            disabled={saving}
          >
            {saving ? '…' : '保存'}
          </button>
        </div>
        {saveMsg && <div className={styles.saveMsg}>{saveMsg}</div>}
      </div>
    </div>
  );
}

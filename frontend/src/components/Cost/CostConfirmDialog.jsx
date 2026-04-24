import React from 'react';
import styles from './CostConfirmDialog.module.css';

/**
 * 高成本操作确认弹窗
 * Props:
 *   open: boolean
 *   estimatedCost: number  (美元)
 *   estimatedTokens: number
 *   title: string
 *   description: string
 *   onConfirm: () => void
 *   onCancel: () => void
 */
export default function CostConfirmDialog({
  open,
  estimatedCost = 0,
  estimatedTokens = 0,
  title = '确认操作',
  description = '',
  onConfirm,
  onCancel,
}) {
  if (!open) return null;

  const costStr = estimatedCost < 0.0001 ? '<$0.0001' : `$${estimatedCost.toFixed(4)}`;

  return (
    <div className={styles.overlay} onClick={onCancel}>
      <div className={styles.dialog} onClick={e => e.stopPropagation()}>
        <div className={styles.header}>
          <span className={styles.warningIcon}>⚠️</span>
          <h3 className={styles.title}>{title}</h3>
        </div>

        {description && <p className={styles.desc}>{description}</p>}

        <div className={styles.costBox}>
          <div className={styles.costRow}>
            <span className={styles.costLabel}>预估费用</span>
            <span className={styles.costValue}>{costStr}</span>
          </div>
          {estimatedTokens > 0 && (
            <div className={styles.costRow}>
              <span className={styles.costLabel}>预估 Token</span>
              <span className={styles.costValue}>{estimatedTokens.toLocaleString()}</span>
            </div>
          )}
        </div>

        <div className={styles.actions}>
          <button className={styles.cancelBtn} onClick={onCancel}>取消</button>
          <button className={styles.confirmBtn} onClick={onConfirm}>确认继续</button>
        </div>
      </div>
    </div>
  );
}

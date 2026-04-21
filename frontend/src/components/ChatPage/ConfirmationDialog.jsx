import React, { useCallback, useEffect, memo } from 'react';
import styles from './ConfirmationDialog.module.css';

/**
 * 操作确认对话框组件
 * 当后端发送 confirmation_required 消息时弹出，要求用户确认危险操作
 *
 * @param {Object} props
 * @param {boolean} props.visible - 是否显示
 * @param {string} [props.action] - 操作标识
 * @param {string} [props.description] - 操作描述
 * @param {string} [props.level] - 风险等级 'high' | 'medium' | 'low'
 * @param {string} [props.details] - 详细信息
 * @param {Array} [props.options] - 可选项
 * @param {string} [props.originalQuery] - 原始查询文本
 * @param {Function} props.onConfirm - 确认回调
 * @param {Function} props.onCancel - 取消回调
 */
function ConfirmationDialog({
  visible,
  action,
  description,
  level = 'medium',
  details,
  options,
  originalQuery,
  onConfirm,
  onCancel,
}) {
  // ESC 键取消
  useEffect(() => {
    if (!visible) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onCancel?.();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [visible, onCancel]);

  // 遮罩层点击取消
  const handleOverlayClick = useCallback((e) => {
    if (e.target === e.currentTarget) {
      onCancel?.();
    }
  }, [onCancel]);

  const handleConfirm = useCallback(() => {
    onConfirm?.({
      action,
      originalQuery,
    });
  }, [onConfirm, action, originalQuery]);

  const handleCancel = useCallback(() => {
    onCancel?.({
      action,
      originalQuery,
    });
  }, [onCancel, action, originalQuery]);

  if (!visible) return null;

  const levelClass = level === 'high' ? styles.levelHigh
    : level === 'medium' ? styles.levelMedium
    : styles.levelLow;

  return (
    <div className={styles.overlay} onClick={handleOverlayClick}>
      <div className={styles.dialog} role="dialog" aria-modal="true">
        {/* 顶部：警告图标 + 标题 */}
        <div className={styles.header}>
          <div className={`${styles.warningIcon} ${levelClass}`}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
            </svg>
          </div>
          <h3 className={styles.title}>操作确认</h3>
        </div>

        {/* 中部：操作描述 */}
        <div className={styles.body}>
          <p className={styles.description}>{description}</p>
          {details && (
            <p className={styles.details}>{details}</p>
          )}
          {options && options.length > 0 && (
            <div className={styles.optionsList}>
              {options.map((opt, idx) => (
                <span key={idx} className={styles.optionTag}>{opt.label}</span>
              ))}
            </div>
          )}
        </div>

        {/* 底部：取消 + 确认按钮 */}
        <div className={styles.footer}>
          <button className={styles.cancelBtn} onClick={handleCancel}>
            取消
          </button>
          <button className={`${styles.confirmBtn} ${levelClass}`} onClick={handleConfirm}>
            确认执行
          </button>
        </div>
      </div>
    </div>
  );
}

export default memo(ConfirmationDialog);

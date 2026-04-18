import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import useToastStore from '../../stores/toastStore';
import styles from './Toast.module.css';

const ICONS = {
  success: '✓',
  error: '✕',
  warning: '⚠',
  info: 'ℹ',
};

function ToastItem({ toast, onRemove }) {
  const { t } = useTranslation();
  const [exiting, setExiting] = useState(false);

  const handleClose = () => {
    setExiting(true);
    setTimeout(() => onRemove(toast.id), 300);
  };

  // 按 Escape 关闭最顶层 toast
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape') handleClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      className={`${styles.toast} ${styles[toast.type] || ''}`}
      style={exiting ? { opacity: 0, transform: 'translateX(40px)' } : undefined}
      role="alert"
    >
      <span className={styles.icon}>{ICONS[toast.type] || ICONS.info}</span>
      <span className={styles.message}>{toast.message}</span>
      <button className={styles.closeBtn} onClick={handleClose} aria-label={t('common.close')}>
        ×
      </button>
      <div className={styles.progressTrack}>
        <div
          className={styles.progressBar}
          style={{ animationDuration: `${toast.duration}ms` }}
        />
      </div>
    </div>
  );
}

export default function Toast() {
  const toasts = useToastStore(state => state.toasts);
  const removeToast = useToastStore(state => state.removeToast);

  if (toasts.length === 0) return null;

  return (
    <div className={styles.container}>
      {toasts.map(toast => (
        <ToastItem key={toast.id} toast={toast} onRemove={removeToast} />
      ))}
    </div>
  );
}

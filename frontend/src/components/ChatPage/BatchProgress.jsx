import React, { memo } from 'react';
import MarkdownContent from '../../utils/MarkdownRenderer';
import styles from './BatchProgress.module.css';

const BatchProgress = memo(function BatchProgress({
  total,
  progress,
  results,
  summary,
  isComplete,
}) {
  const current = progress || 0;
  const percentage = total > 0 ? Math.round((current / total) * 100) : 0;
  const successCount = results?.filter(r => r.status === 'success').length || 0;

  // 成功图标
  const SuccessIcon = () => (
    <svg
      className={styles.successIcon}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );

  // 失败图标
  const ErrorIcon = () => (
    <svg
      className={styles.errorIcon}
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );

  return (
    <div className={styles.batchProgress}>
      {/* 头部标题 */}
      <div className={styles.header}>
        <span className={styles.title}>批量分析进度</span>
        <span className={`${styles.status} ${isComplete ? styles.statusComplete : ''}`}>
          {isComplete ? '已完成' : '分析中...'}
        </span>
      </div>

      {/* 进度条 */}
      <div className={styles.progressSection}>
        <div className={styles.progressBarContainer}>
          <div
            className={styles.progressBar}
            style={{ width: `${percentage}%` }}
          />
        </div>
        <div className={styles.progressInfo}>
          <span>{current}/{total} 篇完成</span>
          <span className={styles.percentage}>{percentage}%</span>
        </div>
      </div>

      {/* 论文列表 */}
      {results && results.length > 0 ? (
        <div className={styles.paperList}>
          {results.map((result, index) => (
            <div key={result.paper_id || index} className={styles.paperItem}>
              <span className={styles.paperIndex}>{index + 1}</span>
              <span className={styles.paperTitle} title={result.title}>
                {result.title || `论文 ${result.paper_id}`}
              </span>
              <span className={styles.statusIcon}>
                {result.status === 'success' ? <SuccessIcon /> : <ErrorIcon />}
              </span>
            </div>
          ))}
        </div>
      ) : (
        <div className={styles.emptyState}>等待开始...</div>
      )}

      {/* 汇总报告（完成后显示） */}
      {isComplete && summary && (
        <div className={styles.summarySection}>
          <div className={styles.summaryHeader}>
            <span className={styles.summaryTitle}>汇总报告</span>
            <span className={styles.summaryBadge}>
              成功 {successCount}/{total}
            </span>
          </div>
          <div className={styles.summaryContent}>
            <MarkdownContent content={summary} />
          </div>
        </div>
      )}
    </div>
  );
});

export default BatchProgress;

import React, { useState, useEffect, memo, useCallback } from 'react';
import styles from './ThinkingBlock.module.css';

function ThinkingBlockComponent({ content, isThinking }) {
  const [expanded, setExpanded] = useState(false);

  // 思考中时自动展开
  useEffect(() => {
    if (isThinking) {
      setExpanded(true);
    }
  }, [isThinking]);

  const handleToggleExpanded = useCallback(() => {
    setExpanded(prev => !prev);
  }, []);

  if (!content && !isThinking) return null;

  return (
    <div className={styles.thinkingBlock}>
      <button
        className={styles.thinkingHeader}
        onClick={handleToggleExpanded}
        type="button"
      >
        <span className={styles.thinkingIcon}>
          {isThinking ? (
            <svg className={styles.pulseIcon} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2a8 8 0 018 8c0 3.4-2.1 6.3-5 7.5V20a1 1 0 01-1 1h-4a1 1 0 01-1-1v-2.5C6.1 16.3 4 13.4 4 10a8 8 0 018-8z"/>
            </svg>
          ) : (
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 6L9 17l-5-5"/>
            </svg>
          )}
        </span>
        <span className={styles.thinkingLabel}>
          {isThinking ? '思考中...' : '已深度思考'}
        </span>
        <svg
          className={`${styles.arrow} ${expanded ? styles.arrowExpanded : ''}`}
          width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        >
          <path d="M6 9l6 6 6-6"/>
        </svg>
      </button>

      {expanded && (
        <div className={styles.thinkingContent}>
          <div className={styles.thinkingText}>
            {content || ''}
            {isThinking && <span className={styles.cursor}>|</span>}
          </div>
        </div>
      )}
    </div>
  );
}

const ThinkingBlock = memo(ThinkingBlockComponent);
export default ThinkingBlock;

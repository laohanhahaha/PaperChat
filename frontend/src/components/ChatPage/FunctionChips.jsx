import React, { useState, useRef, useEffect } from 'react';
import styles from './FunctionChips.module.css';

// 主要功能芯片
const FUNCTION_CHIPS = [
  { id: 'analyze', label: '论文分析', icon: '📋', tool: 'analyze_paper', placeholder: '描述你想分析的内容...' },
  { id: 'review', label: '文献综述', icon: '📝', tool: 'literature_review', placeholder: '输入综述主题和要求...' },
  { id: 'polish', label: '润色改写', icon: '✨', tool: 'polish_text', placeholder: '粘贴需要润色的文本...' },
  { id: 'search', label: '搜索论文', icon: '🔍', tool: 'search_papers', placeholder: '输入搜索关键词...' },
];

// "更多"中的隐藏功能
const MORE_CHIPS = [
  { id: 'cite', label: '引用格式', icon: '📎', tool: 'cite_paper', placeholder: '选择论文后生成引用...' },
  { id: 'knowledge', label: '知识管理', icon: '💾', tool: 'save_card', placeholder: '输入要保存的知识内容...' },
  { id: 'translate', label: '翻译', icon: '🌐', tool: 'translate', placeholder: '输入需要翻译的文本...' },
  { id: 'explain', label: '术语解释', icon: '📖', tool: 'explain_term', placeholder: '输入需要解释的术语...' },
  { id: 'compare', label: '对比分析', icon: '📊', tool: 'compare_content', placeholder: '描述对比需求...' },
  { id: 'keypoints', label: '核心知识点', icon: '🎯', tool: 'extract_key_points', placeholder: '描述提取范围...' },
  { id: 'outline', label: '生成大纲', icon: '📃', tool: 'generate_outline', placeholder: '输入大纲主题...' },
  { id: 'recent', label: '最近论文', icon: '📚', tool: 'recent_papers', placeholder: '查看最近上传的论文...' },
  { id: 'searchCards', label: '搜索知识库', icon: '🔎', tool: 'search_cards', placeholder: '输入搜索关键词...' },
];

export { FUNCTION_CHIPS, MORE_CHIPS };

export default function FunctionChips({ activeFunction, onSelect, onClear, disabled, thinkingMode = 'quick', onThinkingModeChange }) {
  const effectiveMode = activeFunction ? 'deep' : thinkingMode;
  const isModeLocked = activeFunction !== null;

  const handleThinkingToggle = () => {
    if (isModeLocked || disabled) return;
    onThinkingModeChange(thinkingMode === 'quick' ? 'deep' : 'quick');
  };
  const [showMore, setShowMore] = useState(false);
  const moreBtnRef = useRef(null);
  const panelRef = useRef(null);

  // 点击外部关闭更多面板
  useEffect(() => {
    function handleClickOutside(event) {
      if (
        panelRef.current &&
        !panelRef.current.contains(event.target) &&
        moreBtnRef.current &&
        !moreBtnRef.current.contains(event.target)
      ) {
        setShowMore(false);
      }
    }

    if (showMore) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showMore]);

  const handleChipClick = (chip) => {
    if (disabled) return;

    if (activeFunction?.id === chip.id) {
      // 点击已选中的芯片，取消选中
      onClear();
    } else {
      // 点击未选中的芯片，选中它
      onSelect(chip);
    }
  };

  const handleMoreChipClick = (chip) => {
    if (disabled) return;

    onSelect(chip);
    setShowMore(false);
  };

  const handleClearClick = (e) => {
    e.stopPropagation();
    onClear();
  };

  const toggleMore = () => {
    if (disabled) return;
    setShowMore(!showMore);
  };

  const hasActiveFunction = activeFunction !== null;

  return (
    <div className={`${styles.chipsContainer} ${disabled ? styles.disabled : ''}`}>
      {/* 更多面板 - 绝对定位弹出层 */}
      {showMore && (
        <div ref={panelRef} className={styles.morePanel}>
          <div className={styles.morePanelContent}>
            {MORE_CHIPS.map((chip) => (
              <button
                key={chip.id}
                className={`${styles.chip} ${activeFunction?.id === chip.id ? styles.chipActive : ''}`}
                onClick={() => handleMoreChipClick(chip)}
                type="button"
              >
                <span className={styles.chipIcon}>{chip.icon}</span>
                <span className={styles.chipLabel}>{chip.label}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* 主要功能芯片 */}
      <div className={styles.chipsRow}>
        {/* 思考模式切换 */}
        <button
          className={`${styles.thinkingModeBtn} ${effectiveMode === 'deep' ? styles.thinkingModeDeep : styles.thinkingModeQuick} ${isModeLocked ? styles.thinkingModeLocked : ''}`}
          onClick={handleThinkingToggle}
          type="button"
          title={effectiveMode === 'deep' ? '深度思考模式' : '快速模式'}
        >
          {effectiveMode === 'deep' ? (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2a8 8 0 018 8c0 3.4-2.1 6.3-5 7.5V20a1 1 0 01-1 1h-4a1 1 0 01-1-1v-2.5C6.1 16.3 4 13.4 4 10a8 8 0 018-8z"/>
                <path d="M10 22h4"/>
              </svg>
              <span>深度思考</span>
            </>
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
              </svg>
              <span>快速</span>
            </>
          )}
          {/* 展开箭头 */}
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <path d="M6 9l6 6 6-6"/>
          </svg>
        </button>
        <div className={styles.modeDivider} />
        {FUNCTION_CHIPS.map((chip) => {
          const isActive = activeFunction?.id === chip.id;
          const isInactive = hasActiveFunction && !isActive;

          return (
            <button
              key={chip.id}
              className={`${styles.chip} ${isActive ? styles.chipActive : ''} ${isInactive ? styles.chipInactive : ''}`}
              onClick={() => handleChipClick(chip)}
              type="button"
            >
              <span className={styles.chipIcon}>{chip.icon}</span>
              <span className={styles.chipLabel}>{chip.label}</span>
              {isActive && (
                <span className={styles.closeBtn} onClick={handleClearClick}>
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <path d="M18 6L6 18M6 6l12 12" />
                  </svg>
                </span>
              )}
            </button>
          );
        })}

        {/* 更多按钮 */}
        <button
          ref={moreBtnRef}
          className={`${styles.chip} ${styles.moreBtn} ${showMore ? styles.moreBtnActive : ''}`}
          onClick={toggleMore}
          type="button"
        >
          <span className={styles.moreIcon}>⋯</span>
          <span className={styles.chipLabel}>更多</span>
        </button>
      </div>
    </div>
  );
}

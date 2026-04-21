import React, { useState, useCallback, memo } from 'react';
import styles from './ClarificationCard.module.css';

/**
 * 澄清提问卡片组件
 * 用于展示需要用户澄清的问题和选项
 * 
 * @param {Object} props
 * @param {string} props.content - 问题文本
 * @param {Array<{label: string, value: string}>} props.options - 选项列表
 * @param {Function} props.onSelect - 选择回调 (value, label) => void
 * @param {Function} [props.sendMessage] - WebSocket 发送函数
 * @param {string} [props.originalQuery] - 原始查询文本
 */
function ClarificationCard({ content, options, onSelect, sendMessage, originalQuery }) {
  const [selectedValue, setSelectedValue] = useState(null);
  const [customInput, setCustomInput] = useState('');
  const [showCustomInput, setShowCustomInput] = useState(false);

  const handleOptionClick = useCallback((option) => {
    if (selectedValue !== null) return; // 已选择则不再响应

    if (option.value === 'custom') {
      setShowCustomInput(true);
    } else {
      setSelectedValue(option.value);
      // 发送澄清回复给后端
      sendMessage?.('clarification_response', {
        original_query: originalQuery || '',
        response: option.label,
        selected_options: [option],
      });
      onSelect?.(option.value, option.label);
    }
  }, [selectedValue, onSelect, sendMessage, originalQuery]);

  const handleCustomSubmit = useCallback(() => {
    if (!customInput.trim() || selectedValue !== null) return;
    
    const customOption = { label: customInput.trim(), value: 'custom' };
    setSelectedValue('custom');
    // 发送澄清回复给后端
    sendMessage?.('clarification_response', {
      original_query: originalQuery || '',
      response: customInput.trim(),
      selected_options: [customOption],
    });
    onSelect?.('custom', customInput.trim());
  }, [customInput, selectedValue, onSelect, sendMessage, originalQuery]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleCustomSubmit();
    }
  }, [handleCustomSubmit]);

  const isAnswered = selectedValue !== null;

  return (
    <div className={styles.card}>
      {/* 问题文本区域 */}
      <div className={styles.questionBlock}>
        <div className={styles.questionIcon}>?</div>
        <p className={styles.questionText}>{content}</p>
      </div>

      {/* 选项列表 */}
      <div className={styles.optionsList}>
        {options.map((option) => {
          const isSelected = selectedValue === option.value;
          const isDisabled = isAnswered && !isSelected;
          const isCustomOption = option.value === 'custom';

          return (
            <div key={option.value} className={styles.optionWrapper}>
              <button
                className={`${styles.optionBtn} ${
                  isSelected ? styles.optionSelected : ''
                } ${isDisabled ? styles.optionDisabled : ''}`}
                onClick={() => handleOptionClick(option)}
                disabled={isAnswered}
              >
                <span className={styles.optionLabel}>{option.label}</span>
                {isSelected && (
                  <span className={styles.checkIcon}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M5 12l5 5L20 7" />
                    </svg>
                  </span>
                )}
              </button>

              {/* 自定义输入框 */}
              {isCustomOption && showCustomInput && !isAnswered && (
                <div className={styles.customInputWrapper}>
                  <textarea
                    className={styles.customTextarea}
                    value={customInput}
                    onChange={(e) => setCustomInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="请输入您的回答..."
                    rows={2}
                    autoFocus
                  />
                  <button
                    className={`${styles.sendBtn} ${
                      customInput.trim() ? styles.sendBtnActive : ''
                    }`}
                    onClick={handleCustomSubmit}
                    disabled={!customInput.trim()}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
                    </svg>
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* 已回答提示 */}
      {isAnswered && (
        <div className={styles.answeredHint}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M5 12l5 5L20 7" />
          </svg>
          <span>已回答</span>
        </div>
      )}
    </div>
  );
}

export default memo(ClarificationCard);

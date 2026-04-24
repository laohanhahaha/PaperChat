import React from 'react';

export default function InputBar({
  input,
  setInput,
  textareaRef,
  handleKeyDown,
  handleSend,
  handleStop,
  isChatting,
  hasPapers,
  isWelcome,
  enableSearch,
  toggleSearch,
  searchStatus,
  wsStatus,
  onOpenSelector,
  styles,
  costSlot,
}) {
  return (
    <div className={styles.inputWrapper}>
      <div className={styles.inputBox}>
        <button
          className={styles.attachBtn}
          onClick={onOpenSelector}
          title="选择论文"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
          </svg>
        </button>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={hasPapers ? '输入你的问题...' : '请先选择论文...'}
          rows={1}
          disabled={isChatting || (isWelcome && !hasPapers)}
        />
        {isChatting ? (
          <button className={`${styles.sendBtn} ${styles.stopBtn}`} onClick={handleStop} title="停止生成">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          </button>
        ) : (
          <button
            className={`${styles.sendBtn} ${input.trim() ? styles.sendBtnActive : ''}`}
            onClick={() => handleSend()}
            disabled={!input.trim() || (isWelcome && !hasPapers)}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        )}
      </div>
      <div className={styles.inputActions}>
        <label className={styles.searchToggle}>
          <input type="checkbox" checked={enableSearch} onChange={toggleSearch} disabled={isChatting} />
          <span className={styles.toggleDot}></span>
          <span>联网搜索</span>
        </label>
        {searchStatus === 'searching' && (
          <span className={styles.searchingHint}><span className={styles.dot}></span>搜索中...</span>
        )}
        {searchStatus === 'completed' && (
          <span className={styles.searchDoneHint}>✓ 已获取网络信息</span>
        )}
        {wsStatus !== 'connected' && (
          <span className={styles.wsHint}>⚠ 连接中...</span>
        )}
        {costSlot && <div style={{ marginLeft: 'auto', display: 'flex', gap: '6px', alignItems: 'center' }}>{costSlot}</div>}
      </div>
    </div>
  );
}

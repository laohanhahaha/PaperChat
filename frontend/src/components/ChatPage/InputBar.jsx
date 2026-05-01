import React, { useRef, useCallback } from 'react';
import ImagePreview from './ImagePreview';
import FunctionChips from './FunctionChips';

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
  images = [],
  onAddImage,
  onRemoveImage,
  activeFunction,
  onSelectFunction,
  onClearFunction,
  thinkingMode,
  onThinkingModeChange,
}) {
  const fileInputRef = useRef(null);
  const hasUploading = images.some((img) => img.status === 'uploading');

  const handleImageSelect = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback((e) => {
    const file = e.target.files?.[0];
    if (file && onAddImage) {
      onAddImage(file);
    }
    e.target.value = '';
  }, [onAddImage]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    const files = e.dataTransfer?.files;
    if (!files || !onAddImage) return;
    for (const file of files) {
      if (file.type.startsWith('image/')) {
        onAddImage(file);
        break;
      }
    }
  }, [onAddImage]);

  const handlePaste = useCallback((e) => {
    if (!onAddImage) return;
    const items = e.clipboardData?.items;
    if (!items) return;
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        const file = item.getAsFile();
        if (file) {
          onAddImage(file);
          break;
        }
      }
    }
  }, [onAddImage]);

  const isSendDisabled =
    !input.trim() || hasUploading;

  return (
    <div
      className={styles.inputWrapper}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
      onPaste={handlePaste}
    >
      {images.length > 0 && (
        <ImagePreview images={images} onRemove={onRemoveImage} />
      )}
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
        <button
          className={styles.attachBtn}
          onClick={handleImageSelect}
          title="上传图片"
          disabled={isChatting}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <polyline points="21 15 16 10 5 21" />
          </svg>
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          style={{ display: 'none' }}
          onChange={handleFileChange}
        />
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={activeFunction?.placeholder || '输入你的问题...'}
          rows={1}
          disabled={isChatting}
        />
        {isChatting ? (
          <button className={`${styles.sendBtn} ${styles.stopBtn}`} onClick={handleStop} title="停止生成">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          </button>
        ) : (
          <button
            className={`${styles.sendBtn} ${input.trim() && !hasUploading ? styles.sendBtnActive : ''}`}
            onClick={() => handleSend()}
            disabled={isSendDisabled}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        )}
      </div>
      <FunctionChips
        activeFunction={activeFunction}
        onSelect={onSelectFunction}
        onClear={onClearFunction}
        disabled={isChatting}
        thinkingMode={thinkingMode}
        onThinkingModeChange={onThinkingModeChange}
      />
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

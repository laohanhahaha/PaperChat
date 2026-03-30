import { useState, useEffect, useRef } from 'react';
import styles from './NoteEditor.module.css';

/**
 * 笔记编辑器组件
 * 弹窗式笔记编辑器，用于创建和编辑笔记
 * 
 * Props:
 * - isOpen: boolean 是否显示
 * - onClose: () => void 关闭回调
 * - onSave: (content) => void 保存回调
 * - onDelete: () => void 删除回调（可选，编辑已有笔记时）
 * - initialContent: string 初始内容
 * - highlightText: string 关联的高亮文本（可选）
 * - isEditing: boolean 是否是编辑模式
 */
function NoteEditor({ 
  isOpen, 
  onClose, 
  onSave, 
  onDelete,
  initialContent = '', 
  highlightText = null,
  isEditing = false
}) {
  const [content, setContent] = useState(initialContent);
  const [isSaving, setIsSaving] = useState(false);
  const textareaRef = useRef(null);
  const modalRef = useRef(null);

  // 当编辑器打开时，设置初始内容并聚焦
  useEffect(() => {
    if (isOpen) {
      setContent(initialContent);
      // 延迟聚焦，等待动画完成
      setTimeout(() => {
        textareaRef.current?.focus();
        // 如果是编辑模式，将光标移到末尾
        if (isEditing && textareaRef.current) {
          const length = textareaRef.current.value.length;
          textareaRef.current.setSelectionRange(length, length);
        }
      }, 100);
    }
  }, [isOpen, initialContent, isEditing]);

  // 点击外部关闭
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e) => {
      if (modalRef.current && !modalRef.current.contains(e.target)) {
        onClose?.();
      }
    };

    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose?.();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleEscape);

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, onClose]);

  const handleSave = async () => {
    if (!content.trim()) return;
    
    setIsSaving(true);
    try {
      await onSave?.(content.trim());
      onClose?.();
    } catch (error) {
      console.error('保存笔记失败:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!isEditing || !onDelete) return;
    
    if (window.confirm('确定要删除这条笔记吗？')) {
      try {
        await onDelete?.();
        onClose?.();
      } catch (error) {
        console.error('删除笔记失败:', error);
      }
    }
  };

  // 处理快捷键
  const handleKeyDown = (e) => {
    // Ctrl/Cmd + Enter 保存
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSave();
    }
  };

  if (!isOpen) return null;

  return (
    <div className={styles.overlay}>
      <div className={styles.modal} ref={modalRef}>
        <div className={styles.header}>
          <h3 className={styles.title}>
            {isEditing ? '编辑笔记' : '添加笔记'}
          </h3>
          <button className={styles.closeBtn} onClick={onClose} title="关闭 (Esc)">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>

        {/* 高亮文本预览 */}
        {highlightText && (
          <div className={styles.highlightPreview}>
            <div className={styles.highlightLabel}>
              <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                <path d="M3 5h18v2H3V5zm0 6h12v2H3v-2zm0 6h18v2H3v-2z"/>
              </svg>
              关联文本
            </div>
            <div className={styles.highlightText} title={highlightText}>
              {highlightText.length > 150 ? highlightText.substring(0, 150) + '...' : highlightText}
            </div>
          </div>
        )}

        {/* 编辑区域 */}
        <div className={styles.content}>
          <textarea
            ref={textareaRef}
            className={styles.textarea}
            value={content}
            onChange={(e) => setContent(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="在此输入笔记内容..."
            rows={6}
          />
        </div>

        {/* 底部操作栏 */}
        <div className={styles.footer}>
          <div className={styles.hint}>
            <kbd>Ctrl</kbd> + <kbd>Enter</kbd> 保存
          </div>
          <div className={styles.actions}>
            {isEditing && onDelete && (
              <button 
                className={`${styles.btn} ${styles.deleteBtn}`}
                onClick={handleDelete}
                disabled={isSaving}
              >
                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                  <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                </svg>
                删除
              </button>
            )}
            <button 
              className={`${styles.btn} ${styles.cancelBtn}`}
              onClick={onClose}
              disabled={isSaving}
            >
              取消
            </button>
            <button 
              className={`${styles.btn} ${styles.saveBtn}`}
              onClick={handleSave}
              disabled={!content.trim() || isSaving}
            >
              {isSaving ? (
                <>
                  <span className={styles.spinner} />
                  保存中...
                </>
              ) : (
                <>
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                  </svg>
                  保存
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default NoteEditor;

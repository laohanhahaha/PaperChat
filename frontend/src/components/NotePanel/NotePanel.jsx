import { useState, useCallback, useMemo } from 'react';
import styles from './NotePanel.module.css';

/**
 * 笔记面板组件
 * 展示当前论文所有笔记的列表，支持搜索和跳转
 * 
 * Props:
 * - notes: array 笔记列表
 * - onNoteClick: (note) => void 点击笔记回调
 * - onAddNote: () => void 添加笔记回调
 * - onEditNote: (note) => void 编辑笔记回调
 * - onDeleteNote: (note) => void 删除笔记回调
 * - activeNoteId: number 当前选中笔记ID
 * - loading: boolean 加载状态
 */
function NotePanel({ 
  notes = [], 
  onNoteClick,
  onAddNote,
  onEditNote,
  onDeleteNote,
  activeNoteId = null,
  loading = false
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedNotes, setExpandedNotes] = useState(new Set());

  // 过滤笔记
  const filteredNotes = useMemo(() => {
    if (!searchQuery.trim()) return notes;
    
    const query = searchQuery.toLowerCase();
    return notes.filter(note => 
      note.content.toLowerCase().includes(query) ||
      (note.highlight_text && note.highlight_text.toLowerCase().includes(query))
    );
  }, [notes, searchQuery]);

  // 切换笔记展开状态
  const toggleExpand = useCallback((noteId, e) => {
    e.stopPropagation();
    setExpandedNotes(prev => {
      const newSet = new Set(prev);
      if (newSet.has(noteId)) {
        newSet.delete(noteId);
      } else {
        newSet.add(noteId);
      }
      return newSet;
    });
  }, []);

  // 格式化日期
  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now - date;
    
    // 小于1小时显示"X分钟前"
    if (diff < 60 * 60 * 1000) {
      const minutes = Math.floor(diff / (60 * 1000));
      return minutes < 1 ? '刚刚' : `${minutes}分钟前`;
    }
    
    // 小于24小时显示"X小时前"
    if (diff < 24 * 60 * 60 * 1000) {
      const hours = Math.floor(diff / (60 * 60 * 1000));
      return `${hours}小时前`;
    }
    
    // 小于7天显示"X天前"
    if (diff < 7 * 24 * 60 * 60 * 1000) {
      const days = Math.floor(diff / (24 * 60 * 60 * 1000));
      return `${days}天前`;
    }
    
    // 否则显示日期
    return date.toLocaleDateString('zh-CN', { 
      month: 'short', 
      day: 'numeric' 
    });
  };

  // 获取笔记内容摘要
  const getNoteSummary = (content, maxLength = 80) => {
    if (content.length <= maxLength) return content;
    return content.substring(0, maxLength) + '...';
  };

  // 处理笔记点击
  const handleNoteClick = (note) => {
    onNoteClick?.(note);
  };

  // 处理编辑
  const handleEdit = (note, e) => {
    e.stopPropagation();
    onEditNote?.(note);
  };

  // 处理删除
  const handleDelete = (note, e) => {
    e.stopPropagation();
    if (window.confirm('确定要删除这条笔记吗？')) {
      onDeleteNote?.(note);
    }
  };

  return (
    <div className={styles.container}>
      {/* 头部 */}
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <h3 className={styles.title}>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
            </svg>
            笔记列表
          </h3>
          <span className={styles.count}>{notes.length}</span>
        </div>
        <button className={styles.addBtn} onClick={onAddNote} title="添加新笔记">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
          </svg>
        </button>
      </div>

      {/* 搜索框 */}
      <div className={styles.searchBox}>
        <svg className={styles.searchIcon} viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
        </svg>
        <input
          type="text"
          className={styles.searchInput}
          placeholder="搜索笔记..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        {searchQuery && (
          <button 
            className={styles.clearBtn}
            onClick={() => setSearchQuery('')}
            title="清除搜索"
          >
            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        )}
      </div>

      {/* 笔记列表 */}
      <div className={styles.noteList}>
        {loading ? (
          <div className={styles.emptyState}>
            <div className={styles.spinner} />
            <span>加载中...</span>
          </div>
        ) : filteredNotes.length === 0 ? (
          <div className={styles.emptyState}>
            {searchQuery ? (
              <>
                <svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor" opacity="0.5">
                  <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
                </svg>
                <span>未找到匹配的笔记</span>
              </>
            ) : (
              <>
                <svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor" opacity="0.5">
                  <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
                </svg>
                <span>暂无笔记</span>
                <button className={styles.emptyAddBtn} onClick={onAddNote}>
                  添加第一条笔记
                </button>
              </>
            )}
          </div>
        ) : (
          filteredNotes.map((note) => {
            const isExpanded = expandedNotes.has(note.id);
            const isActive = activeNoteId === note.id;
            const hasHighlight = !!note.highlight_id;
            
            return (
              <div
                key={note.id}
                className={`${styles.noteItem} ${isActive ? styles.active : ''}`}
                onClick={() => handleNoteClick(note)}
              >
                {/* 关联高亮指示器 */}
                {hasHighlight && (
                  <div className={styles.highlightIndicator} title="关联高亮文本">
                    <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor">
                      <path d="M3 5h18v2H3V5zm0 6h12v2H3v-2zm0 6h18v2H3v-2z"/>
                    </svg>
                  </div>
                )}
                
                {/* 笔记内容 */}
                <div className={styles.noteContent}>
                  {hasHighlight && note.highlight_text && (
                    <div className={styles.highlightText} title={note.highlight_text}>
                      "{note.highlight_text.length > 60 
                        ? note.highlight_text.substring(0, 60) + '...' 
                        : note.highlight_text}"
                    </div>
                  )}
                  <div className={styles.noteText}>
                    {isExpanded ? note.content : getNoteSummary(note.content)}
                  </div>
                </div>

                {/* 底部信息 */}
                <div className={styles.noteFooter}>
                  <span className={styles.noteTime}>{formatDate(note.created_at)}</span>
                  
                  <div className={styles.noteActions}>
                    {/* 展开/收起按钮 */}
                    {note.content.length > 80 && (
                      <button
                        className={styles.actionBtn}
                        onClick={(e) => toggleExpand(note.id, e)}
                        title={isExpanded ? '收起' : '展开'}
                      >
                        <svg 
                          viewBox="0 0 24 24" 
                          width="14" 
                          height="14" 
                          fill="currentColor"
                          style={{ transform: isExpanded ? 'rotate(180deg)' : 'none' }}
                        >
                          <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z"/>
                        </svg>
                      </button>
                    )}
                    
                    {/* 编辑按钮 */}
                    <button
                      className={styles.actionBtn}
                      onClick={(e) => handleEdit(note, e)}
                      title="编辑"
                    >
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                        <path d="M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04c.39-.39.39-1.02 0-1.41l-2.34-2.34c-.39-.39-1.02-.39-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z"/>
                      </svg>
                    </button>
                    
                    {/* 删除按钮 */}
                    <button
                      className={`${styles.actionBtn} ${styles.deleteAction}`}
                      onClick={(e) => handleDelete(note, e)}
                      title="删除"
                    >
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                        <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export default NotePanel;

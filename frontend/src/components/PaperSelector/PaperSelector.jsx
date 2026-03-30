import { useState, useEffect, useMemo } from 'react';
import usePaperStore from '../../stores/paperStore';
import styles from './PaperSelector.module.css';

// 阅读状态映射
const STATUS_MAP = {
  unread: { label: '未读', color: '#6b7280' },
  reading: { label: '阅读中', color: '#f59e0b' },
  finished: { label: '已完成', color: '#10b981' },
};

// 格式化日期
const formatDate = (dateString) => {
  const date = new Date(dateString);
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

function PaperSelector({ isOpen, onClose, onConfirm, initialSelectedIds = [], maxSelection = 10 }) {
  const { papers, loading, fetchPapers } = usePaperStore();
  const [selectedIds, setSelectedIds] = useState(initialSelectedIds);
  const [searchQuery, setSearchQuery] = useState('');

  // 加载论文列表
  useEffect(() => {
    if (isOpen && papers.length === 0) {
      fetchPapers({ page: 1, page_size: 100 });
    }
  }, [isOpen, papers.length, fetchPapers]);

  // 同步初始选中状态
  useEffect(() => {
    setSelectedIds(initialSelectedIds);
  }, [initialSelectedIds, isOpen]);

  // 过滤论文
  const filteredPapers = useMemo(() => {
    if (!searchQuery.trim()) return papers;
    const query = searchQuery.toLowerCase();
    return papers.filter(paper => 
      paper.title.toLowerCase().includes(query) ||
      (paper.authors && paper.authors.toLowerCase().includes(query))
    );
  }, [papers, searchQuery]);

  // 切换选中状态
  const toggleSelection = (paperId) => {
    setSelectedIds(prev => {
      if (prev.includes(paperId)) {
        return prev.filter(id => id !== paperId);
      }
      if (prev.length >= maxSelection) {
        return prev; // 已达到最大选择数
      }
      return [...prev, paperId];
    });
  };

  // 确认选择
  const handleConfirm = () => {
    onConfirm(selectedIds);
    onClose();
  };

  // 取消选择
  const handleCancel = () => {
    setSelectedIds(initialSelectedIds);
    setSearchQuery('');
    onClose();
  };

  // 全选当前过滤结果
  const handleSelectAll = () => {
    const availableSlots = maxSelection - selectedIds.length;
    if (availableSlots <= 0) return;
    
    const unselectedPapers = filteredPapers.filter(p => !selectedIds.includes(p.id));
    const toSelect = unselectedPapers.slice(0, availableSlots).map(p => p.id);
    setSelectedIds(prev => [...prev, ...toSelect]);
  };

  // 清空选择
  const handleClearAll = () => {
    setSelectedIds([]);
  };

  if (!isOpen) return null;

  return (
    <div className={styles.overlay} onClick={handleCancel}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* 头部 */}
        <div className={styles.header}>
          <h3>选择论文</h3>
          <button className={styles.closeBtn} onClick={handleCancel}>×</button>
        </div>

        {/* 搜索栏 */}
        <div className={styles.searchBar}>
          <svg className={styles.searchIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder="搜索标题或作者..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className={styles.searchInput}
          />
          {searchQuery && (
            <button 
              className={styles.clearSearch}
              onClick={() => setSearchQuery('')}
            >
              ×
            </button>
          )}
        </div>

        {/* 选择统计 */}
        <div className={styles.stats}>
          <span className={styles.selectedCount}>
            已选择 <strong>{selectedIds.length}</strong> / {maxSelection} 篇
          </span>
          <div className={styles.actions}>
            <button 
              className={styles.actionBtn}
              onClick={handleSelectAll}
              disabled={selectedIds.length >= maxSelection || filteredPapers.length === 0}
            >
              全选
            </button>
            <button 
              className={styles.actionBtn}
              onClick={handleClearAll}
              disabled={selectedIds.length === 0}
            >
              清空
            </button>
          </div>
        </div>

        {/* 论文列表 */}
        <div className={styles.paperList}>
          {loading ? (
            <div className={styles.loading}>
              <div className={styles.spinner}></div>
              <p>加载中...</p>
            </div>
          ) : filteredPapers.length === 0 ? (
            <div className={styles.empty}>
              {searchQuery ? '没有找到匹配的论文' : '暂无论文'}
            </div>
          ) : (
            filteredPapers.map(paper => {
              const isSelected = selectedIds.includes(paper.id);
              const isDisabled = !isSelected && selectedIds.length >= maxSelection;
              
              return (
                <div
                  key={paper.id}
                  className={`${styles.paperItem} ${isSelected ? styles.selected : ''} ${isDisabled ? styles.disabled : ''}`}
                  onClick={() => !isDisabled && toggleSelection(paper.id)}
                >
                  <div className={styles.checkbox}>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}}
                      disabled={isDisabled}
                    />
                    {isSelected && (
                      <svg className={styles.checkIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </div>
                  
                  <div className={styles.paperInfo}>
                    <div className={styles.paperHeader}>
                      <h4 className={styles.paperTitle} title={paper.title}>
                        {paper.title}
                      </h4>
                      <span 
                        className={styles.statusBadge}
                        style={{ 
                          backgroundColor: `${STATUS_MAP[paper.reading_status]?.color}20`,
                          color: STATUS_MAP[paper.reading_status]?.color 
                        }}
                      >
                        {STATUS_MAP[paper.reading_status]?.label || paper.reading_status}
                      </span>
                    </div>
                    
                    {paper.authors && (
                      <p className={styles.paperAuthors} title={paper.authors}>
                        {paper.authors}
                      </p>
                    )}
                    
                    <div className={styles.paperMeta}>
                      <span>{paper.page_count} 页</span>
                      <span>·</span>
                      <span>{formatDate(paper.created_at)}</span>
                      {paper.category && (
                        <>
                          <span>·</span>
                          <span className={styles.category}>{paper.category}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* 底部按钮 */}
        <div className={styles.footer}>
          <button 
            className={styles.cancelBtn}
            onClick={handleCancel}
          >
            取消
          </button>
          <button 
            className={styles.confirmBtn}
            onClick={handleConfirm}
            disabled={selectedIds.length < 2}
          >
            确认选择 ({selectedIds.length}篇)
          </button>
        </div>
      </div>
    </div>
  );
}

export default PaperSelector;

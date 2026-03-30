import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import usePaperStore from '../../stores/paperStore';
import styles from './Recommendations.module.css';

// 阅读状态映射
const STATUS_MAP = {
  unread: { label: '未读', color: '#6b7280' },
  reading: { label: '阅读中', color: '#f59e0b' },
  finished: { label: '已完成', color: '#10b981' },
};

/**
 * 推荐论文组件
 * 
 * @param {Object} props
 * @param {Array} props.papers - 推荐论文列表
 * @param {string} props.title - 标题（默认"相关推荐"）
 * @param {string} props.layout - 布局模式：'horizontal' | 'vertical'（默认 vertical）
 * @param {boolean} props.loading - 加载状态
 * @param {boolean} props.collapsible - 是否可折叠（默认 true）
 * @param {boolean} props.defaultCollapsed - 默认是否折叠（默认 false）
 * @param {Function} props.onRefresh - 刷新回调
 * @param {string} props.emptyText - 空状态提示文本
 * @param {number} props.paperId - 当前论文ID（用于网络推荐）
 * @param {boolean} props.showWebRecommendations - 是否显示网络推荐区域
 */
function Recommendations({
  papers = [],
  title = '相关推荐',
  layout = 'vertical',
  loading = false,
  collapsible = true,
  defaultCollapsed = false,
  onRefresh,
  emptyText = '暂无推荐论文',
  paperId,
  showWebRecommendations = false
}) {
  const navigate = useNavigate();
  const [isCollapsed, setIsCollapsed] = useState(defaultCollapsed);
  
  // 网络学术推荐状态
  const { 
    webRecommendations, 
    webRecommendationsLoading, 
    fetchWebRecommendations, 
    clearWebRecommendations 
  } = usePaperStore();

  const handlePaperClick = (paperId) => {
    navigate(`/reader/${paperId}`);
  };

  // 渲染相似度指示器
  const renderSimilarity = (similarity) => {
    if (similarity === null || similarity === undefined) return null;
    
    // 根据相似度设置颜色
    let color = '#6b7280';
    if (similarity >= 80) color = '#10b981';
    else if (similarity >= 60) color = '#3b82f6';
    else if (similarity >= 40) color = '#f59e0b';
    
    return (
      <div className={styles.similarityBadge} style={{ backgroundColor: `${color}20`, color }}>
        <svg className={styles.similarityIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <span>{similarity}% 匹配</span>
      </div>
    );
  };

  // 渲染匹配原因标签
  const renderMatchReason = (reason) => {
    if (!reason) return null;
    
    return (
      <span className={styles.matchReason}>
        {reason}
      </span>
    );
  };

  if (loading) {
    return (
      <div className={`${styles.container} ${styles[layout]}`}>
        <div className={styles.header}>
          <h3 className={styles.title}>{title}</h3>
        </div>
        <div className={styles.loading}>
          <div className={styles.spinner}></div>
          <span>加载推荐...</span>
        </div>
      </div>
    );
  }

  if (!papers || papers.length === 0) {
    return (
      <div className={`${styles.container} ${styles[layout]}`}>
        <div className={styles.header}>
          <h3 className={styles.title}>{title}</h3>
        </div>
        <div className={styles.empty}>
          <svg className={styles.emptyIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          <p>{emptyText}</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.container} ${styles[layout]}`}>
      <div className={styles.header}>
        <h3 className={styles.title}>{title}</h3>
        <div className={styles.headerActions}>
          {onRefresh && (
            <button 
              className={styles.refreshBtn}
              onClick={onRefresh}
              title="刷新推荐"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          )}
          {collapsible && (
            <button 
              className={styles.collapseBtn}
              onClick={() => setIsCollapsed(!isCollapsed)}
              title={isCollapsed ? '展开' : '折叠'}
            >
              <svg 
                viewBox="0 0 24 24" 
                fill="none" 
                stroke="currentColor"
                style={{ transform: isCollapsed ? 'rotate(180deg)' : 'none' }}
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          )}
        </div>
      </div>
      
      {!isCollapsed && (
        <div className={styles.paperList}>
          {papers.map((paper) => (
            <div
              key={paper.id}
              className={styles.paperCard}
              onClick={() => handlePaperClick(paper.id)}
            >
              <div className={styles.cardHeader}>
                {renderSimilarity(paper.similarity)}
                {paper.match_reason && renderMatchReason(paper.match_reason)}
                {!paper.similarity && !paper.match_reason && paper.reading_status && (
                  <span 
                    className={styles.statusBadge}
                    style={{ 
                      backgroundColor: `${STATUS_MAP[paper.reading_status]?.color}20`,
                      color: STATUS_MAP[paper.reading_status]?.color 
                    }}
                  >
                    {STATUS_MAP[paper.reading_status]?.label || paper.reading_status}
                  </span>
                )}
              </div>
              
              <h4 className={styles.paperTitle} title={paper.title}>
                {paper.title}
              </h4>
              
              {paper.authors && (
                <p className={styles.paperAuthors} title={paper.authors}>
                  {paper.authors}
                </p>
              )}
              
              {paper.abstract_preview && (
                <p className={styles.abstractPreview}>
                  {paper.abstract_preview}
                </p>
              )}
              
              <div className={styles.cardFooter}>
                <span className={styles.metaInfo}>
                  {paper.page_count > 0 && `${paper.page_count} 页`}
                  {paper.category && ` · ${paper.category}`}
                </span>
                <svg className={styles.arrowIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </div>
          ))}
        </div>
      )}
      
      {/* 网络学术推荐区域 */}
      {showWebRecommendations && paperId && (
        <div className={styles.webSection}>
          <div className={styles.webSectionHeader}>
            <h4>🔗 网络学术推荐</h4>
            <button 
              className={styles.searchBtn}
              onClick={() => fetchWebRecommendations(paperId)}
              disabled={webRecommendationsLoading}
            >
              {webRecommendationsLoading ? '搜索中...' : '搜索相关文献'}
            </button>
          </div>
          
          {webRecommendationsLoading && (
            <div className={styles.webLoading}>
              <div className={styles.loadingSpinner}></div>
              <span>正在搜索学术网络...</span>
            </div>
          )}
          
          {webRecommendations.length > 0 && (
            <div className={styles.webResults}>
              {webRecommendations.map((result, idx) => (
                <a 
                  key={idx}
                  href={result.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.webResultCard}
                >
                  <div className={styles.webResultTitle}>
                    {result.title}
                    <span className={styles.externalIcon}>↗</span>
                  </div>
                  {result.abstract && (
                    <p className={styles.webResultAbstract}>
                      {result.abstract.length > 150 
                        ? result.abstract.slice(0, 150) + '...' 
                        : result.abstract}
                    </p>
                  )}
                  <div className={styles.webResultMeta}>
                    <span className={styles.sourceBadge}>{result.source}</span>
                  </div>
                </a>
              ))}
            </div>
          )}
          
          {!webRecommendationsLoading && webRecommendations.length === 0 && (
            <p className={styles.webHint}>点击上方按钮搜索网络上的相关学术文献</p>
          )}
        </div>
      )}
    </div>
  );
}

export default Recommendations;

import { useState, useEffect, useCallback, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import { useTranslation } from 'react-i18next';
import usePaperStore from '../stores/paperStore';
import BatchImport from '../components/BatchImport/BatchImport';
import BatchAnalysis from '../components/BatchAnalysis/BatchAnalysis';
import Recommendations from '../components/Recommendations/Recommendations';
import RecommendationPanel from '../components/Recommendations/RecommendationPanel';
import styles from './PaperList.module.css';

// 阅读状态映射
const STATUS_MAP = {
  unread: { label: '未读', color: '#6b7280' },
  reading: { label: '已阅读', color: '#10b981' },
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

// 格式化阅读时间（精确到分钟）
const formatReadTime = (dateString) => {
  if (!dateString) return null;
  const d = new Date(dateString);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const hour = String(d.getHours()).padStart(2, '0');
  const minute = String(d.getMinutes()).padStart(2, '0');
  return `${year}-${month}-${day} ${hour}:${minute}`;
};

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};

// 论文卡片组件 - 使用 React.memo 优化渲染性能
const PaperCard = memo(({ paper, onNavigate, onDeleteClick }) => {
  return (
    <div
      className={styles.paperCard}
      onClick={() => onNavigate(paper.id)}
    >
      <div className={styles.cardHeader}>
        <div className={styles.statusSection}>
          <span
            className={styles.statusBadge}
            style={{
              backgroundColor: `${STATUS_MAP[paper.reading_status]?.color}20`,
              color: STATUS_MAP[paper.reading_status]?.color
            }}
          >
            {STATUS_MAP[paper.reading_status]?.label || paper.reading_status}
          </span>
          {paper.last_read_at && (
            <span className={styles.readTime}>
              最后阅读: {formatReadTime(paper.last_read_at)}
            </span>
          )}
        </div>
        <button
          className={styles.deleteBtn}
          onClick={(e) => {
            e.stopPropagation();
            onDeleteClick(paper);
          }}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>

      <h3 className={styles.paperTitle} title={paper.title}>
        {paper.title}
      </h3>

      {paper.authors && (
        <p className={styles.paperAuthors} title={paper.authors}>
          {paper.authors}
        </p>
      )}

      {/* 关键词标签 */}
      {paper.tags && (() => {
        try {
          const tags = typeof paper.tags === 'string' ? JSON.parse(paper.tags) : paper.tags;
          if (!Array.isArray(tags) || tags.length === 0) return null;
          return (
            <div className={styles.tagsContainer}>
              {tags.slice(0, 4).map((tag, idx) => (
                <span key={idx} className={styles.keywordTag}>{tag}</span>
              ))}
              {tags.length > 4 && <span className={styles.tagMore}>+{tags.length - 4}</span>}
            </div>
          );
        } catch { return null; }
      })()}

      <div className={styles.cardFooter}>
        <span className={styles.paperMeta}>
          {paper.page_count} 页 · {formatFileSize(paper.file_size)}
        </span>
        <span className={styles.paperDate}>
          {formatDate(paper.created_at)}
        </span>
      </div>

      {paper.category && (
        <span className={styles.categoryTag}>{paper.category}</span>
      )}
    </div>
  );
});

function PaperList() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { 
    papers, 
    total, 
    loading, 
    error, 
    fetchPapers, 
    uploadPaper, 
    deletePaper,
    clearError,
    personalRecommendations,
    personalRecommendationsLoading,
    fetchPersonalRecommendations
  } = usePaperStore();

  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [showBatchImport, setShowBatchImport] = useState(false);
  const [showBatchAnalysis, setShowBatchAnalysis] = useState(false);
  const [, setUploadProgress] = useState(0);
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const pageSize = 12;

  // 加载论文列表
  const loadPapers = useCallback(async () => {
    try {
      await fetchPapers({
        page,
        page_size: pageSize,
        search: search || undefined,
        category: category || undefined,
        reading_status: status || undefined,
      });
    } catch (err) {
      console.error('加载论文列表失败:', err);
    }
  }, [fetchPapers, page, pageSize, search, category, status]);

  // 加载论文列表
  useEffect(() => {
    loadPapers();
  }, [loadPapers]);

  // 加载个性化推荐
  useEffect(() => {
    fetchPersonalRecommendations(5).catch(err => {
      console.error('加载个性化推荐失败:', err);
    });
  }, [fetchPersonalRecommendations]);

  // 搜索防抖
  useEffect(() => {
    const timer = setTimeout(() => {
      if (page !== 1) {
        setPage(1);
      } else {
        loadPapers();
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [search, page, loadPapers]);

  // 文件上传
  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;
    
    const file = acceptedFiles[0];
    setUploadProgress(0);
    
    try {
      const paper = await uploadPaper(file, {
        title: file.name.replace('.pdf', ''),
      });
      setShowUploadModal(false);
      // 跳转到阅读页面
      navigate(`/reader/${paper.id}`);
    } catch (err) {
      console.error('上传失败:', err);
    }
  }, [uploadPaper, navigate]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxSize: 50 * 1024 * 1024,
    multiple: false,
  });

  // 删除论文
  const handleDelete = async (id) => {
    try {
      await deletePaper(id);
      setDeleteConfirm(null);
    } catch (err) {
      console.error('删除失败:', err);
    }
  };

  // 使用 useCallback 包装回调函数，确保 prop 稳定
  const handleNavigateToPaper = useCallback((paperId) => {
    navigate(`/reader/${paperId}`);
  }, [navigate]);

  const handleDeleteClick = useCallback((paper) => {
    setDeleteConfirm(paper);
  }, []);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className={styles.container}>
      {/* 头部 */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.logo}>PaperChat</h1>
          <span className={styles.subtitle}>文献管理系统</span>
        </div>
        <div className={styles.headerRight}>
          <button 
            className={styles.uploadBtn}
            onClick={() => setShowUploadModal(true)}
          >
            <svg className={styles.icon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            {t('paper.upload')}
          </button>
          <button 
            className={styles.batchImportBtn}
            onClick={() => setShowBatchImport(true)}
          >
            <svg className={styles.icon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
            批量导入
          </button>
          <button
            className={styles.batchAnalysisBtn}
            onClick={() => setShowBatchAnalysis(true)}
          >
            <svg className={styles.icon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            批量分析
          </button>
        </div>
      </header>

      {/* 个性化推荐区块 */}
      <div className={styles.recommendationsSection}>
          <Recommendations
            papers={personalRecommendations}
            title="为你推荐"
            loading={personalRecommendationsLoading}
            layout="horizontal"
            collapsible={true}
            defaultCollapsed={false}
            onRefresh={() => fetchPersonalRecommendations(5)}
            emptyText="上传更多论文以获取个性化推荐"
          />
        </div>

      {/* 综合推荐面板（知识图谱 + 内容相似 + 个性化融合） */}
      <div className={styles.recommendationsSection}>
        <RecommendationPanel
          title="智能综合推荐"
          topK={8}
          collapsed={true}
        />
      </div>

      {/* 搜索和筛选栏 */}
      <div className={styles.filterBar}>
        <div className={styles.searchBox}>
          <svg className={styles.searchIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            placeholder={t('common.search') + '...'}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={styles.searchInput}
          />
        </div>
        
        <select 
          value={category} 
          onChange={(e) => setCategory(e.target.value)}
          className={styles.filterSelect}
        >
          <option value="">全部分类</option>
          <option value="计算机科学">计算机科学</option>
          <option value="人工智能">人工智能</option>
          <option value="机器学习">机器学习</option>
          <option value="自然语言处理">自然语言处理</option>
          <option value="其他">其他</option>
        </select>
        
        <select 
          value={status} 
          onChange={(e) => setStatus(e.target.value)}
          className={styles.filterSelect}
        >
          <option value="">全部状态</option>
          <option value="unread">未读</option>
          <option value="reading">阅读中</option>
          <option value="finished">已完成</option>
        </select>
      </div>

      {/* 错误提示 */}
      {error && (
        <div className={styles.errorBanner}>
          {error}
          <button onClick={clearError} className={styles.closeError}>×</button>
        </div>
      )}

      {/* 论文列表 */}
      {loading && papers.length === 0 ? (
        <div className={styles.loading}>加载中...</div>
      ) : papers.length === 0 ? (
        <div className={styles.empty}>
          <div className={styles.emptyIcon}>📚</div>
          <h3>{t('common.noData')}</h3>
          <p>点击上方"上传论文"按钮添加你的第一篇论文</p>
        </div>
      ) : (
        <>
          <div className={styles.paperGrid}>
            {papers.map((paper) => (
              <PaperCard
                key={paper.id}
                paper={paper}
                onNavigate={handleNavigateToPaper}
                onDeleteClick={handleDeleteClick}
              />
            ))}
          </div>

          {/* 分页 */}
          {totalPages > 1 && (
            <div className={styles.pagination}>
              <button
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
                className={styles.pageBtn}
              >
                上一页
              </button>
              <span className={styles.pageInfo}>
                第 {page} / {totalPages} 页
              </span>
              <button
                disabled={page === totalPages}
                onClick={() => setPage(page + 1)}
                className={styles.pageBtn}
              >
                下一页
              </button>
            </div>
          )}
        </>
      )}

      {/* 上传弹窗 */}
      {showUploadModal && (
        <div className={styles.modalOverlay} onClick={() => setShowUploadModal(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>上传论文</h3>
              <button 
                className={styles.modalClose}
                onClick={() => setShowUploadModal(false)}
              >
                ×
              </button>
            </div>
            <div 
              {...getRootProps()} 
              className={`${styles.uploadDropzone} ${isDragActive ? styles.active : ''}`}
            >
              <input {...getInputProps()} />
              <div className={styles.uploadIcon}>📄</div>
              <p className={styles.uploadText}>
                {isDragActive ? '释放文件以上传' : '拖拽 PDF 文件到此处'}
              </p>
              <p className={styles.uploadHint}>或点击选择文件（最大 50MB）</p>
            </div>
          </div>
        </div>
      )}

      {/* 批量导入弹窗 */}
      {showBatchImport && (
        <BatchImport 
          onClose={() => setShowBatchImport(false)} 
          onSuccess={() => {
            loadPapers();
          }}
        />
      )}

      {/* 批量分析弹窗 */}
      {showBatchAnalysis && (
        <BatchAnalysis onClose={() => setShowBatchAnalysis(false)} />
      )}

      {/* 删除确认弹窗 */}
      {deleteConfirm && (
        <div className={styles.modalOverlay} onClick={() => setDeleteConfirm(null)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div className={styles.modalHeader}>
              <h3>确认删除</h3>
              <button 
                className={styles.modalClose}
                onClick={() => setDeleteConfirm(null)}
              >
                ×
              </button>
            </div>
            <p className={styles.confirmText}>
              确定要删除论文 "{deleteConfirm.title}" 吗？此操作不可恢复。
            </p>
            <div className={styles.modalActions}>
              <button 
                className={styles.cancelBtn}
                onClick={() => setDeleteConfirm(null)}
              >
                取消
              </button>
              <button 
                className={styles.confirmBtn}
                onClick={() => handleDelete(deleteConfirm.id)}
              >
                删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default PaperList;

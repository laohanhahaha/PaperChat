import { useState, useEffect, useCallback, useRef } from 'react';
import usePaperStore from '../../stores/paperStore';
import {
  submitBatchAnalysis,
  getBatchStatus,
  getBatchResults,
  cancelBatch,
} from '../../api/batchAnalysisApi';
import styles from './BatchAnalysis.module.css';

const ANALYSIS_TYPES = [
  { value: 'summary', label: '批量摘要', desc: '为每篇论文独立生成摘要' },
  { value: 'compare', label: '对比分析', desc: '对所选论文进行多维度横向对比' },
  { value: 'review', label: '批量综述', desc: '基于所选论文生成文献综述' },
];

const STATUS_LABELS = {
  pending: '等待中',
  running: '分析中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

const STATUS_COLORS = {
  pending: '#6b7280',
  running: '#B8860B',
  completed: '#10b981',
  failed: '#ef4444',
  cancelled: '#9ca3af',
};

export default function BatchAnalysis({ onClose }) {
  const { papers, fetchPapers } = usePaperStore();

  // 选中的论文 ID
  const [selectedIds, setSelectedIds] = useState(new Set());
  // 分析类型
  const [analysisType, setAnalysisType] = useState('summary');
  // 当前任务 ID
  const [batchId, setBatchId] = useState(null);
  // 任务状态
  const [batchData, setBatchData] = useState(null);
  // 加载/提交状态
  const [submitting, setSubmitting] = useState(false);
  // 展开的论文结果
  const [expandedIds, setExpandedIds] = useState(new Set());
  // 轮询定时器
  const pollRef = useRef(null);

  // 加载论文列表
  useEffect(() => {
    fetchPapers({ page: 1, page_size: 100 }).catch(() => {});
  }, [fetchPapers]);

  // 轮询进度
  const startPolling = useCallback((id) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const data = await getBatchStatus(id);
        setBatchData(data);
        if (['completed', 'failed', 'cancelled'].includes(data.status)) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          // 拉取完整结果
          const full = await getBatchResults(id);
          setBatchData(full);
        }
      } catch {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }, 2000);
  }, []);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const toggleSelect = (id) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleAll = () => {
    if (selectedIds.size === papers.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(papers.map((p) => p.id)));
    }
  };

  const handleSubmit = async () => {
    if (selectedIds.size === 0) return;
    setSubmitting(true);
    setBatchData(null);
    setBatchId(null);
    try {
      const res = await submitBatchAnalysis([...selectedIds], analysisType);
      setBatchId(res.batch_id);
      startPolling(res.batch_id);
    } catch {
      // axios 拦截器已 toast 错误
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async () => {
    if (!batchId) return;
    try {
      await cancelBatch(batchId);
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      const data = await getBatchStatus(batchId);
      setBatchData(data);
    } catch {}
  };

  const toggleExpand = (id) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const isRunning = batchData && ['pending', 'running'].includes(batchData.status);
  const isDone = batchData && ['completed', 'failed', 'cancelled'].includes(batchData.status);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.panel} onClick={(e) => e.stopPropagation()}>
        {/* 标题栏 */}
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <svg className={styles.headerIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
            <h2 className={styles.title}>批量分析</h2>
          </div>
          <button className={styles.closeBtn} onClick={onClose}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className={styles.body}>
          {/* 左侧：设置区 */}
          <div className={styles.left}>
            {/* 分析类型 */}
            <section className={styles.section}>
              <h3 className={styles.sectionTitle}>分析类型</h3>
              <div className={styles.typeList}>
                {ANALYSIS_TYPES.map((t) => (
                  <label key={t.value} className={`${styles.typeItem} ${analysisType === t.value ? styles.typeSelected : ''}`}>
                    <input
                      type="radio"
                      name="analysisType"
                      value={t.value}
                      checked={analysisType === t.value}
                      onChange={() => setAnalysisType(t.value)}
                      className={styles.hiddenRadio}
                      disabled={isRunning}
                    />
                    <span className={styles.typeLabel}>{t.label}</span>
                    <span className={styles.typeDesc}>{t.desc}</span>
                  </label>
                ))}
              </div>
            </section>

            {/* 论文选择 */}
            <section className={styles.section}>
              <div className={styles.sectionHeader}>
                <h3 className={styles.sectionTitle}>选择论文</h3>
                <div className={styles.sectionMeta}>
                  <span className={styles.selectedCount}>{selectedIds.size} / {papers.length}</span>
                  <button className={styles.selectAllBtn} onClick={toggleAll} disabled={isRunning}>
                    {selectedIds.size === papers.length ? '取消全选' : '全选'}
                  </button>
                </div>
              </div>

              <div className={styles.paperList}>
                {papers.length === 0 ? (
                  <p className={styles.emptyTip}>暂无论文，请先上传</p>
                ) : (
                  papers.map((paper) => (
                    <label key={paper.id} className={`${styles.paperItem} ${selectedIds.has(paper.id) ? styles.paperSelected : ''}`}>
                      <input
                        type="checkbox"
                        checked={selectedIds.has(paper.id)}
                        onChange={() => toggleSelect(paper.id)}
                        className={styles.checkbox}
                        disabled={isRunning}
                      />
                      <span className={styles.paperTitle}>{paper.title}</span>
                    </label>
                  ))
                )}
              </div>
            </section>

            {/* 操作按钮 */}
            <div className={styles.actions}>
              {!isRunning && (
                <button
                  className={styles.submitBtn}
                  onClick={handleSubmit}
                  disabled={selectedIds.size === 0 || submitting}
                >
                  {submitting ? '提交中...' : '开始分析'}
                </button>
              )}
              {isRunning && (
                <button className={styles.cancelBtn} onClick={handleCancel}>
                  取消任务
                </button>
              )}
            </div>
          </div>

          {/* 右侧：进度 + 结果区 */}
          <div className={styles.right}>
            {!batchData ? (
              <div className={styles.placeholder}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className={styles.placeholderIcon}>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                    d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                <p>选择论文并点击"开始分析"</p>
              </div>
            ) : (
              <>
                {/* 总进度 */}
                <div className={styles.progressBlock}>
                  <div className={styles.progressHeader}>
                    <span className={styles.progressLabel}>
                      {ANALYSIS_TYPES.find((t) => t.value === batchData.analysis_type)?.label || batchData.analysis_type}
                    </span>
                    <span
                      className={styles.statusBadge}
                      style={{ color: STATUS_COLORS[batchData.status] }}
                    >
                      {STATUS_LABELS[batchData.status] || batchData.status}
                    </span>
                  </div>
                  <div className={styles.progressBarWrap}>
                    <div
                      className={styles.progressBar}
                      style={{
                        width: `${batchData.progress}%`,
                        background: batchData.status === 'failed' ? '#ef4444'
                          : batchData.status === 'cancelled' ? '#9ca3af'
                          : '#B8860B',
                      }}
                    />
                  </div>
                  <div className={styles.progressStats}>
                    <span>进度 {batchData.progress}%</span>
                    <span>{batchData.completed} 完成 · {batchData.failed} 失败 · 共 {batchData.total}</span>
                  </div>
                </div>

                {/* 整体结果（compare / review）*/}
                {batchData.combined_result && (
                  <div className={styles.combinedResult}>
                    <h4 className={styles.combinedTitle}>
                      {batchData.analysis_type === 'compare' ? '对比分析结果' : '文献综述结果'}
                    </h4>
                    <pre className={styles.combinedContent}>{batchData.combined_result}</pre>
                  </div>
                )}

                {/* 每篇论文状态 */}
                <div className={styles.paperResults}>
                  {batchData.paper_results.map((pr) => (
                    <div key={pr.paper_id} className={styles.paperResultItem}>
                      <div
                        className={styles.paperResultHeader}
                        onClick={() => pr.result && toggleExpand(pr.paper_id)}
                      >
                        <span className={styles.paperResultTitle}>{pr.paper_title}</span>
                        <span
                          className={styles.paperResultStatus}
                          style={{ color: STATUS_COLORS[pr.status] }}
                        >
                          {STATUS_LABELS[pr.status] || pr.status}
                        </span>
                        {pr.result && (
                          <svg
                            className={`${styles.expandIcon} ${expandedIds.has(pr.paper_id) ? styles.expanded : ''}`}
                            viewBox="0 0 24 24" fill="none" stroke="currentColor"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        )}
                      </div>
                      {pr.error && (
                        <p className={styles.errorText}>{pr.error}</p>
                      )}
                      {pr.result && expandedIds.has(pr.paper_id) && (
                        <pre className={styles.resultContent}>{pr.result}</pre>
                      )}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

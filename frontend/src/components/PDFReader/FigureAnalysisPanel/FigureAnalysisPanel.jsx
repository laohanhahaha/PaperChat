import { useState, useRef, useEffect } from 'react';
import styles from './FigureAnalysisPanel.module.css';

/**
 * FigureAnalysisPanel — 图表分析侧边面板
 *
 * props:
 *   visible: boolean
 *   figure: {bbox, type, label, page, base64?}
 *   analysisResult: {chart_type, data_summary, key_findings, raw_description} | null
 *   loading: boolean
 *   onClose: () => void
 *   onAskQuestion: (question: string) => void
 */
const FigureAnalysisPanel = ({
  visible,
  figure,
  analysisResult,
  loading,
  onClose,
  onAskQuestion,
}) => {
  const [question, setQuestion] = useState('');
  const panelRef = useRef(null);

  useEffect(() => {
    if (!visible) return;

    const handleClickOutside = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        onClose?.();
      }
    };

    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 100);

    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [visible, onClose]);

  const handleSendQuestion = () => {
    const q = question.trim();
    if (!q) return;
    onAskQuestion?.(q);
    setQuestion('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendQuestion();
    }
  };

  if (!visible) return null;

  return (
    <div ref={panelRef} className={styles.panel}>
      {/* 标题栏 */}
      <div className={styles.header}>
        <span className={styles.title}>
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zM9 17H7v-7h2v7zm4 0h-2V7h2v10zm4 0h-2v-4h2v4z" />
          </svg>
          图表分析
        </span>
        <button className={styles.closeBtn} onClick={onClose} title="关闭">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
          </svg>
        </button>
      </div>

      {/* 内容区域 */}
      <div className={styles.content}>
        {/* 图表信息 */}
        {figure && (
          <div className={styles.figureInfo}>
            <div className={styles.figureMeta}>
              <span className={`${styles.typeTag} ${styles[figure.type]}`}>
                {figure.type === 'table' ? '表格' : '图表'}
              </span>
              <span className={styles.labelText}>{figure.label}</span>
              <span className={styles.pageText}>第 {figure.page} 页</span>
            </div>

            {/* 图表原图 */}
            {figure.base64 ? (
              <div className={styles.imageWrapper}>
                <img
                  src={`data:image/png;base64,${figure.base64}`}
                  alt={figure.label}
                  className={styles.figureImage}
                />
              </div>
            ) : (
              <div className={styles.imagePlaceholder}>
                <svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor">
                  <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z" />
                </svg>
                <span>暂无可视化预览</span>
              </div>
            )}
          </div>
        )}

        {/* 加载状态 */}
        {loading && (
          <div className={styles.loading}>
            <div className={styles.spinner} />
            <span>正在分析图表...</span>
          </div>
        )}

        {/* 分析结果 */}
        {!loading && analysisResult && (
          <div className={styles.result}>
            {analysisResult.chart_type && (
              <div className={styles.resultSection}>
                <h4 className={styles.sectionTitle}>图表类型</h4>
                <p className={styles.sectionText}>{analysisResult.chart_type}</p>
              </div>
            )}

            {analysisResult.data_summary && (
              <div className={styles.resultSection}>
                <h4 className={styles.sectionTitle}>数据摘要</h4>
                <p className={styles.sectionText}>{analysisResult.data_summary}</p>
              </div>
            )}

            {analysisResult.key_findings?.length > 0 && (
              <div className={styles.resultSection}>
                <h4 className={styles.sectionTitle}>关键发现</h4>
                <ul className={styles.findingsList}>
                  {analysisResult.key_findings.map((finding, idx) => (
                    <li key={idx} className={styles.findingItem}>
                      {finding}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {analysisResult.raw_description && (
              <div className={styles.resultSection}>
                <h4 className={styles.sectionTitle}>详细描述</h4>
                <p className={styles.sectionText}>{analysisResult.raw_description}</p>
              </div>
            )}
          </div>
        )}

        {/* 空状态 */}
        {!loading && !analysisResult && figure && (
          <div className={styles.empty}>
            <span>点击图表开始分析</span>
          </div>
        )}
      </div>

      {/* 追问输入 */}
      <div className={styles.footer}>
        <div className={styles.inputWrapper}>
          <input
            type="text"
            className={styles.questionInput}
            placeholder="追问关于此图表的问题..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <button
            className={styles.sendBtn}
            onClick={handleSendQuestion}
            disabled={!question.trim() || loading}
            title="发送"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};

export default FigureAnalysisPanel;

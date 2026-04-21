import React, { useState, useEffect, useCallback, useRef, memo } from 'react';
import { citationApi } from '../../api/citationApi';
import styles from './CitationPanel.module.css';

/**
 * 引用管理面板组件
 * 侧边栏面板，展示论文引用信息，支持多种格式切换、复制和导出
 * 
 * Props:
 * - paperId: number | string 当前论文ID
 * - onClose: () => void 关闭面板回调
 */
function CitationPanelComponent({ paperId, onClose }) {
  const [citationData, setCitationData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeFormat, setActiveFormat] = useState('bibtex'); // 'bibtex' | 'apa' | 'gbt'
  const [copied, setCopied] = useState(false);
  const [exporting, setExporting] = useState(false);
  const panelRef = useRef(null);
  const copiedTimerRef = useRef(null);

  // 加载引用数据
  useEffect(() => {
    if (!paperId) return;

    const fetchCitation = async () => {
      setLoading(true);
      setError(null);
      try {
        const res = await citationApi.getCitation(paperId);
        setCitationData(res.data);
      } catch (err) {
        console.error('加载引用信息失败:', err);
        setError('加载引用信息失败');
      } finally {
        setLoading(false);
      }
    };

    fetchCitation();
  }, [paperId]);

  // 清理定时器
  useEffect(() => {
    return () => {
      if (copiedTimerRef.current) {
        clearTimeout(copiedTimerRef.current);
      }
    };
  }, []);

  // 获取当前格式的引用文本
  const getCurrentCitationText = useCallback(() => {
    if (!citationData) return '';
    switch (activeFormat) {
      case 'bibtex': return citationData.bibtex || '';
      case 'apa': return citationData.apa || '';
      case 'gbt': return citationData.gbt || '';
      default: return citationData.bibtex || '';
    }
  }, [citationData, activeFormat]);

  // 复制到剪贴板
  const handleCopy = useCallback(async () => {
    const text = getCurrentCitationText();
    if (!text) return;

    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      if (copiedTimerRef.current) {
        clearTimeout(copiedTimerRef.current);
      }
      copiedTimerRef.current = setTimeout(() => {
        setCopied(false);
      }, 2000);
    } catch (err) {
      console.error('复制失败:', err);
      // fallback
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      copiedTimerRef.current = setTimeout(() => setCopied(false), 2000);
    }
  }, [getCurrentCitationText]);

  // 导出引用文件
  const handleExport = useCallback(async () => {
    if (!paperId) return;

    setExporting(true);
    try {
      // 直接使用 activeFormat 作为格式参数（'bibtex'/'apa'/'gbt'）
      const format = activeFormat;
      const res = await citationApi.exportCitations([paperId], format);
      const content = res.data.content;

      // 根据格式确定文件扩展名和 MIME 类型
      let filename, mimeType;
      if (activeFormat === 'bibtex') {
        filename = `citation_${paperId}.bib`;
        mimeType = 'application/x-bibtex';
      } else {
        filename = `citation_${paperId}.txt`;
        mimeType = 'text/plain;charset=utf-8';
      }

      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('导出引用失败:', err);
      // 降级：使用本地数据导出
      const text = getCurrentCitationText();
      if (text) {
        let filename, mimeType;
        if (activeFormat === 'bibtex') {
          filename = `citation_${paperId}.bib`;
          mimeType = 'application/x-bibtex';
        } else {
          filename = `citation_${paperId}.txt`;
          mimeType = 'text/plain;charset=utf-8';
        }

        const blob = new Blob([text], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    } finally {
      setExporting(false);
    }
  }, [paperId, activeFormat, getCurrentCitationText]);

  // 点击遮罩关闭
  const handleOverlayClick = useCallback((e) => {
    if (e.target === e.currentTarget) {
      onClose?.();
    }
  }, [onClose]);

  // ESC 键关闭
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose?.();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // 格式标签配置
  const formatTabs = [
    { key: 'bibtex', label: 'BibTeX' },
    { key: 'apa', label: 'APA' },
    { key: 'gbt', label: 'GB/T 7714' },
  ];

  // 渲染元数据字段
  const renderMetadata = () => {
    if (!citationData?.metadata) return null;

    const { metadata } = citationData;
    const fields = [
      { key: 'title', label: '标题', icon: '📄' },
      { key: 'authors', label: '作者', icon: '👤' },
      { key: 'year', label: '年份', icon: '📅' },
      { key: 'venue', label: '会议/期刊', icon: '🏛' },
      { key: 'doi', label: 'DOI', icon: '🔗' },
    ];

    return (
      <div className={styles.metadataSection}>
        <h4 className={styles.sectionTitle}>论文信息</h4>
        <div className={styles.metadataList}>
          {fields.map(({ key, label, icon }) => {
            const value = metadata[key];
            if (!value) return null;

            const displayValue = Array.isArray(value) ? value.join(', ') : value;

            return (
              <div key={key} className={styles.metadataItem}>
                <span className={styles.metaIcon}>{icon}</span>
                <div className={styles.metaContent}>
                  <span className={styles.metaLabel}>{label}</span>
                  {key === 'doi' ? (
                    <a
                      className={styles.metaValue}
                      href={`https://doi.org/${displayValue}`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {displayValue}
                    </a>
                  ) : (
                    <span className={styles.metaValue}>{displayValue}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  // 渲染引用格式区域
  const renderCitationContent = () => {
    const text = getCurrentCitationText();

    return (
      <div className={styles.citationSection}>
        <h4 className={styles.sectionTitle}>引用格式</h4>

        {/* 格式切换 Tab */}
        <div className={styles.formatTabs}>
          {formatTabs.map(({ key, label }) => (
            <button
              key={key}
              className={`${styles.formatTab} ${activeFormat === key ? styles.formatTabActive : ''}`}
              onClick={() => setActiveFormat(key)}
            >
              {label}
            </button>
          ))}
        </div>

        {/* 引用文本 */}
        <div className={styles.codeBlock}>
          {text ? (
            <pre className={styles.codeText}>{text}</pre>
          ) : (
            <span className={styles.codeEmpty}>暂无该格式的引用数据</span>
          )}
        </div>

        {/* 操作按钮 */}
        <div className={styles.actions}>
          <button
            className={styles.actionBtn}
            onClick={handleCopy}
            disabled={!text}
            title="复制引用文本"
          >
            {copied ? (
              <>
                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                  <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                </svg>
                已复制
              </>
            ) : (
              <>
                <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                  <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
                </svg>
                复制
              </>
            )}
          </button>
          <button
            className={`${styles.actionBtn} ${styles.exportBtn}`}
            onClick={handleExport}
            disabled={!text || exporting}
            title="导出引用文件"
          >
            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
              <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
            </svg>
            {exporting ? '导出中...' : '导出'}
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className={styles.overlay} onClick={handleOverlayClick}>
      <div className={styles.panel} ref={panelRef}>
        {/* 面板头部 */}
        <div className={styles.header}>
          <div className={styles.headerTitle}>
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
            </svg>
            <h3 className={styles.title}>引用信息</h3>
          </div>
          <button className={styles.closeBtn} onClick={onClose} title="关闭">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>

        {/* 面板内容 */}
        <div className={styles.content}>
          {loading ? (
            <div className={styles.loading}>
              <div className={styles.spinner} />
              <span>加载引用信息...</span>
            </div>
          ) : error ? (
            <div className={styles.error}>
              <svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor" opacity="0.5">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
              </svg>
              <span>{error}</span>
              <button className={styles.retryBtn} onClick={() => {
                setLoading(true);
                setError(null);
                citationApi.getCitation(paperId).then(res => {
                  setCitationData(res.data);
                }).catch(() => {
                  setError('加载引用信息失败');
                }).finally(() => setLoading(false));
              }}>
                重试
              </button>
            </div>
          ) : (
            <>
              {renderMetadata()}
              {renderCitationContent()}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

const CitationPanel = memo(CitationPanelComponent);
export default CitationPanel;

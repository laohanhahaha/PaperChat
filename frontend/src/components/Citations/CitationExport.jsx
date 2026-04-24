import { useState, useCallback, useEffect, useRef } from 'react';
import { citationApi } from '../../api/citationApi';
import styles from './CitationExport.module.css';

const FORMAT_OPTIONS = [
  { key: 'bibtex', label: 'BibTeX', ext: 'bib' },
  { key: 'ris', label: 'RIS', ext: 'ris' },
  { key: 'apa', label: 'APA', ext: 'txt' },
  { key: 'mla', label: 'MLA', ext: 'txt' },
  { key: 'chicago', label: 'Chicago', ext: 'txt' },
  { key: 'gbt7714', label: 'GB/T 7714', ext: 'txt' },
];

/**
 * 引用导出弹窗组件
 * Props:
 * - paperIds: number[] 选中的论文 ID 列表
 * - onClose: () => void 关闭回调
 */
function CitationExport({ paperIds, onClose }) {
  const [format, setFormat] = useState('bibtex');
  const [preview, setPreview] = useState('');
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [zoteroStatus, setZoteroStatus] = useState(null);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const copiedTimerRef = useRef(null);

  // 加载时自动预览
  useEffect(() => {
    if (paperIds.length > 0) {
      handlePreview(format);
    }
    checkZoteroStatus();
  }, []);

  // 格式切换时重新预览
  useEffect(() => {
    if (paperIds.length > 0) {
      handlePreview(format);
    }
  }, [format]);

  const checkZoteroStatus = async () => {
    try {
      const res = await citationApi.getZoteroStatus();
      setZoteroStatus(res.data);
    } catch {
      setZoteroStatus({ configured: false, connected: false });
    }
  };

  const handlePreview = useCallback(async (fmt) => {
    if (!paperIds.length) return;
    setLoading(true);
    setError('');
    try {
      const res = await citationApi.exportCitations(paperIds, fmt);
      setPreview(res.data.content || '');
    } catch (err) {
      console.error('预览引用失败:', err);
      setError('预览失败，请重试');
      setPreview('');
    } finally {
      setLoading(false);
    }
  }, [paperIds]);

  const handleExport = useCallback(async () => {
    if (!paperIds.length || !preview) return;

    const fmt = FORMAT_OPTIONS.find(f => f.key === format);
    const filename = `citations_${paperIds.length}.${fmt?.ext || 'txt'}`;
    const mimeType = format === 'bibtex'
      ? 'application/x-bibtex'
      : format === 'ris'
        ? 'application/x-research-info-systems'
        : 'text/plain;charset=utf-8';

    const blob = new Blob([preview], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [paperIds, preview, format]);

  const handleCopy = useCallback(async () => {
    if (!preview) return;
    try {
      await navigator.clipboard.writeText(preview);
      setCopied(true);
      if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current);
      copiedTimerRef.current = setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('复制失败:', err);
    }
  }, [preview]);

  const handleSyncZotero = useCallback(async () => {
    if (!paperIds.length) return;
    setSyncing(true);
    setError('');
    try {
      const res = await citationApi.syncToZotero(paperIds);
      const data = res.data;
      if (data.success) {
        alert(`成功同步 ${data.synced} / ${data.total} 篇论文到 Zotero`);
      } else {
        setError(`同步失败: ${data.errors?.join('; ') || '未知错误'}`);
      }
    } catch (err) {
      const msg = err.response?.data?.detail || '同步到 Zotero 失败';
      setError(msg);
    } finally {
      setSyncing(false);
    }
  }, [paperIds]);

  // ESC 关闭
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose?.();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // 清理定时器
  useEffect(() => {
    return () => {
      if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current);
    };
  }, []);

  const zoteroConfigured = zoteroStatus?.configured && zoteroStatus?.connected;

  return (
    <div className={styles.overlay} onClick={(e) => e.target === e.currentTarget && onClose?.()}>
      <div className={styles.modal}>
        {/* 头部 */}
        <div className={styles.header}>
          <h3 className={styles.title}>
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
            </svg>
            导出引用 ({paperIds.length} 篇)
          </h3>
          <button className={styles.closeBtn} onClick={onClose} title="关闭">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>

        {/* 内容 */}
        <div className={styles.content}>
          {/* 格式选择 */}
          <div className={styles.formatRow}>
            <label className={styles.label}>引用格式</label>
            <select
              className={styles.select}
              value={format}
              onChange={(e) => setFormat(e.target.value)}
            >
              {FORMAT_OPTIONS.map(opt => (
                <option key={opt.key} value={opt.key}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* 预览区域 */}
          <div className={styles.previewSection}>
            <div className={styles.previewHeader}>
              <span className={styles.previewLabel}>预览</span>
              <button
                className={styles.copyBtn}
                onClick={handleCopy}
                disabled={!preview || loading}
              >
                {copied ? '已复制' : '复制'}
              </button>
            </div>
            <div className={styles.previewBox}>
              {loading ? (
                <div className={styles.loading}>加载中...</div>
              ) : preview ? (
                <pre className={styles.previewText}>{preview}</pre>
              ) : (
                <div className={styles.empty}>暂无预览内容</div>
              )}
            </div>
          </div>

          {/* 错误提示 */}
          {error && (
            <div className={styles.errorMsg}>{error}</div>
          )}

          {/* 操作按钮 */}
          <div className={styles.actions}>
            <button
              className={styles.exportBtn}
              onClick={handleExport}
              disabled={!preview || loading}
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/>
              </svg>
              下载文件
            </button>

            <button
              className={`${styles.zoteroBtn} ${!zoteroConfigured ? styles.zoteroDisabled : ''}`}
              onClick={handleSyncZotero}
              disabled={!zoteroConfigured || syncing}
              title={!zoteroConfigured ? '请先在设置中配置 Zotero API Key' : '同步到 Zotero'}
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M12 4V1L8 5l4 4V6c3.31 0 6 2.69 6 6 0 1.01-.25 1.97-.7 2.8l1.46 1.46C19.54 15.03 20 13.57 20 12c0-4.42-3.58-8-8-8zm0 14c-3.31 0-6-2.69-6-6 0-1.01.25-1.97.7-2.8L5.24 7.74C4.46 8.97 4 10.43 4 12c0 4.42 3.58 8 8 8v3l4-4-4-4v3z"/>
              </svg>
              {syncing ? '同步中...' : '同步到 Zotero'}
            </button>
          </div>

          {!zoteroConfigured && (
            <div className={styles.zoteroHint}>
              提示：在「设置」中配置 Zotero API Key 和 Library ID 后可启用同步功能
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default CitationExport;

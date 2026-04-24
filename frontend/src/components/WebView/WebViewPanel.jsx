import { useState, useRef, useCallback, useEffect } from 'react';
import styles from './WebViewPanel.module.css';

/**
 * WebViewPanel — 通用 WebView 面板
 *
 * Props:
 *   url            {string}    要加载的 URL
 *   renderContent  {string}    HTML 字符串（srcdoc，与 url 互斥，url 优先）
 *   title          {string}    面板标题
 *   onClose        {function}  关闭回调
 *   sandbox        {string}    iframe sandbox 属性
 *   width          {string}    宽度，默认 "100%"
 *   height         {string}    高度，默认 "600px"
 *   placement      {'side'|'bottom'|'modal'}  展示位置，默认 'side'
 */
function WebViewPanel({
  url,
  renderContent,
  title,
  onClose,
  sandbox = 'allow-scripts allow-same-origin allow-popups allow-forms',
  width = '100%',
  height = '600px',
  placement = 'side',
}) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [currentUrl, setCurrentUrl] = useState(url || '');
  const [inputUrl, setInputUrl] = useState(url || '');
  const [isResizing, setIsResizing] = useState(false);
  const [panelSize, setPanelSize] = useState(null); // null = 使用默认

  const iframeRef = useRef(null);
  const panelRef = useRef(null);
  const resizeStartRef = useRef(null);

  // 当外部 url 变化时同步
  useEffect(() => {
    if (url) {
      setCurrentUrl(url);
      setInputUrl(url);
      setLoading(true);
      setError(false);
    }
  }, [url]);

  const handleLoad = useCallback(() => {
    setLoading(false);
    setError(false);
  }, []);

  const handleError = useCallback(() => {
    setLoading(false);
    setError(true);
  }, []);

  const handleOpenExternal = useCallback(() => {
    const target = currentUrl || url;
    if (target) {
      window.open(target, '_blank', 'noopener,noreferrer');
    }
  }, [currentUrl, url]);

  const handleNavigate = useCallback((e) => {
    e.preventDefault();
    const trimmed = inputUrl.trim();
    if (!trimmed) return;
    const normalized = /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
    setCurrentUrl(normalized);
    setInputUrl(normalized);
    setLoading(true);
    setError(false);
  }, [inputUrl]);

  const handleRefresh = useCallback(() => {
    if (iframeRef.current) {
      setLoading(true);
      setError(false);
      // 重新赋值 src 触发刷新
      const src = iframeRef.current.src;
      iframeRef.current.src = '';
      requestAnimationFrame(() => {
        if (iframeRef.current) iframeRef.current.src = src;
      });
    }
  }, []);

  // ---- 拖拽调整大小 ----
  const handleResizeStart = useCallback((e) => {
    e.preventDefault();
    const rect = panelRef.current?.getBoundingClientRect();
    if (!rect) return;
    setIsResizing(true);
    resizeStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      w: rect.width,
      h: rect.height,
    };

    const onMove = (e) => {
      if (!resizeStartRef.current) return;
      const { x, y, w, h } = resizeStartRef.current;
      if (placement === 'side') {
        const newW = Math.max(280, Math.min(window.innerWidth * 0.8, w - (e.clientX - x)));
        setPanelSize({ width: newW });
      } else if (placement === 'bottom') {
        const newH = Math.max(200, Math.min(window.innerHeight * 0.85, h - (e.clientY - y)));
        setPanelSize({ height: newH });
      }
    };

    const onUp = () => {
      setIsResizing(false);
      resizeStartRef.current = null;
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [placement]);

  // ---- 渲染内容决策 ----
  const isSrcdoc = !url && !!renderContent;
  const displayTitle = title || (isSrcdoc ? '预览' : (currentUrl || '加载中'));

  // ---- 面板尺寸样式 ----
  const panelStyle = {};
  if (placement === 'side') {
    panelStyle.width = panelSize?.width ? `${panelSize.width}px` : width;
    panelStyle.height = '100%';
  } else if (placement === 'bottom') {
    panelStyle.width = '100%';
    panelStyle.height = panelSize?.height ? `${panelSize.height}px` : height;
  } else {
    // modal
    panelStyle.width = width;
    panelStyle.height = height;
  }

  return (
    <div
      className={`${styles.panel} ${styles[`panel--${placement}`]} ${isResizing ? styles['panel--resizing'] : ''}`}
      style={panelStyle}
      ref={panelRef}
    >
      {/* 拖拽手柄 */}
      {(placement === 'side' || placement === 'bottom') && (
        <div
          className={`${styles.resizeHandle} ${styles[`resizeHandle--${placement}`]}`}
          onMouseDown={handleResizeStart}
          title="拖拽调整大小"
        />
      )}

      {/* 顶部工具栏 */}
      <header className={styles.toolbar}>
        <div className={styles.toolbarLeft}>
          <span className={styles.panelIcon}>🌐</span>
          <span className={styles.panelTitle} title={displayTitle}>
            {displayTitle.length > 40 ? displayTitle.slice(0, 40) + '…' : displayTitle}
          </span>
        </div>

        {!isSrcdoc && (
          <form className={styles.urlBar} onSubmit={handleNavigate}>
            <input
              type="text"
              className={styles.urlInput}
              value={inputUrl}
              onChange={(e) => setInputUrl(e.target.value)}
              placeholder="输入 URL 导航..."
              spellCheck={false}
            />
            <button type="submit" className={styles.navBtn} title="导航">↵</button>
          </form>
        )}

        <div className={styles.toolbarActions}>
          {!isSrcdoc && (
            <button
              className={styles.actionBtn}
              onClick={handleRefresh}
              title="刷新"
              disabled={loading}
            >
              ↺
            </button>
          )}
          <button
            className={styles.actionBtn}
            onClick={handleOpenExternal}
            title="在新窗口打开"
          >
            ↗
          </button>
          <button
            className={`${styles.actionBtn} ${styles.closeBtn}`}
            onClick={onClose}
            title="关闭"
          >
            ✕
          </button>
        </div>
      </header>

      {/* 主内容区 */}
      <div className={styles.body}>
        {loading && !error && (
          <div className={styles.loadingOverlay}>
            <div className={styles.spinner} />
            <span className={styles.loadingText}>加载中...</span>
          </div>
        )}

        {error && (
          <div className={styles.errorPane}>
            <div className={styles.errorIcon}>⚠</div>
            <p className={styles.errorTitle}>页面无法加载</p>
            <p className={styles.errorMsg}>
              该页面可能不允许嵌入显示，或网络连接存在问题。
            </p>
            <div className={styles.errorActions}>
              <button className={styles.errorBtn} onClick={handleRefresh}>重试</button>
              <button className={styles.errorBtn} onClick={handleOpenExternal}>在新窗口打开</button>
            </div>
          </div>
        )}

        <iframe
          ref={iframeRef}
          className={`${styles.iframe} ${error ? styles['iframe--hidden'] : ''}`}
          {...(isSrcdoc
            ? { srcDoc: renderContent }
            : { src: currentUrl }
          )}
          title={displayTitle}
          sandbox={sandbox}
          onLoad={handleLoad}
          onError={handleError}
          loading="lazy"
          referrerPolicy="no-referrer"
          allow="fullscreen"
        />
      </div>
    </div>
  );
}

export default WebViewPanel;

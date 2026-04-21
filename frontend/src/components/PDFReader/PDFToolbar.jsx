import styles from './PDFReader.module.css';

/**
 * PDFToolbar - PDF 阅读器工具栏
 * 负责：页码导航、缩放控制、视图模式切换
 */
const PDFToolbar = ({
  pageNumber,
  numPages,
  scale,
  viewMode,
  onPrevPage,
  onNextPage,
  onPageInputChange,
  onZoomIn,
  onZoomOut,
  onFitToWidth,
  onSetViewMode,
}) => {
  return (
    <div className={styles.toolbar}>
      <div className={styles.toolbarGroup}>
        {/* 页码控制 */}
        <button
          className={styles.toolbarBtn}
          onClick={onPrevPage}
          disabled={pageNumber <= 1}
          title="上一页"
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z" />
          </svg>
        </button>

        <div className={styles.pageInfo}>
          <input
            type="number"
            min={1}
            max={numPages || 1}
            value={pageNumber}
            onChange={onPageInputChange}
            className={styles.pageInput}
          />
          <span className={styles.pageTotal}> / {numPages || '-'}</span>
        </div>

        <button
          className={styles.toolbarBtn}
          onClick={onNextPage}
          disabled={pageNumber >= (numPages || 1)}
          title="下一页"
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" />
          </svg>
        </button>
      </div>

      <div className={styles.toolbarDivider} />

      <div className={styles.toolbarGroup}>
        {/* 缩放控制 */}
        <button
          className={styles.toolbarBtn}
          onClick={onZoomOut}
          disabled={scale <= 0.5}
          title="缩小"
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M19 13H5v-2h14v2z" />
          </svg>
        </button>

        <span className={styles.scaleInfo}>{Math.round(scale * 100)}%</span>

        <button
          className={styles.toolbarBtn}
          onClick={onZoomIn}
          disabled={scale >= 3.0}
          title="放大"
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
          </svg>
        </button>

        <button
          className={styles.toolbarBtn}
          onClick={onFitToWidth}
          title="适应宽度"
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M4 6h16v2H4zm0 5h16v2H4zm0 5h16v2H4z" />
          </svg>
        </button>
      </div>

      <div className={styles.toolbarDivider} />

      <div className={styles.toolbarGroup}>
        {/* 视图模式切换 */}
        <button
          className={`${styles.toolbarBtn} ${viewMode === 'single' ? styles.active : ''}`}
          onClick={() => onSetViewMode('single')}
          title="单页模式"
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M4 4h16v16H4z" fill="none" stroke="currentColor" strokeWidth="2"/>
            <path d="M6 6h12v12H6z" />
          </svg>
        </button>
        <button
          className={`${styles.toolbarBtn} ${viewMode === 'scroll' ? styles.active : ''}`}
          onClick={() => onSetViewMode('scroll')}
          title="滚动模式"
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M4 4h16v6H4zm0 8h16v6H4z" fill="none" stroke="currentColor" strokeWidth="2"/>
            <path d="M6 6h12v2H6zm0 8h12v2H6z" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default PDFToolbar;

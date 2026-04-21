import { Page } from 'react-pdf';
import styles from './PDFReader.module.css';
import HighlightLayer from '../HighlightLayer/HighlightLayer';

/**
 * PDFPageRenderer - PDF 页面渲染
 * 支持单页模式和滚动模式（含 IntersectionObserver 懒加载）
 */
const PDFPageRenderer = ({
  viewMode,
  pageNumber,
  numPages,
  scale,
  pageDimensions,
  visiblePages,
  highlights,
  activeHighlight,
  onHighlightClick,
  onMouseUp,
  onPageLoadSuccess,
  registerPageElement,
  pageRefs,
  scrollContainerRef,
  getHighlightsForPage,
}) => {
  const renderSinglePage = () => {
    const pageHighlights = getHighlightsForPage(pageNumber);
    const dims = pageDimensions[pageNumber];

    return (
      <div
        ref={(el) => { pageRefs.current[pageNumber] = el; }}
        className={styles.pageWrapper}
        data-page-number={pageNumber}
        onMouseUp={(e) => onMouseUp(e, pageNumber)}
      >
        <Page
          pageNumber={pageNumber}
          scale={scale}
          renderTextLayer={true}
          renderAnnotationLayer={true}
          onLoadSuccess={(page) => onPageLoadSuccess(page, pageNumber)}
          loading={<div className={styles.pageLoading}>加载中...</div>}
          error={<div className={styles.pageError}>页面加载失败</div>}
        />
        {dims && (
          <HighlightLayer
            highlights={pageHighlights}
            pageNumber={pageNumber}
            scale={scale}
            pageWidth={dims.width}
            pageHeight={dims.height}
            activeHighlight={activeHighlight}
            onHighlightClick={onHighlightClick}
          />
        )}
      </div>
    );
  };

  const renderScrollPages = () => (
    <div ref={scrollContainerRef} className={styles.scrollContainer}>
      {Array.from({ length: numPages || 0 }, (_, i) => i + 1).map((pageNum) => {
        const pageHighlights = getHighlightsForPage(pageNum);
        const dims = pageDimensions[pageNum];
        const isVisible = visiblePages.has(pageNum);
        const pageHeight = dims?.height ? dims.height * scale : 800;

        return (
          <div
            key={pageNum}
            ref={(el) => registerPageElement(el, pageNum)}
            className={styles.pageWrapper}
            data-page={pageNum}
            data-page-number={pageNum}
            onMouseUp={(e) => onMouseUp(e, pageNum)}
            style={{ minHeight: pageHeight }}
          >
            {isVisible ? (
              <>
                <Page
                  pageNumber={pageNum}
                  scale={scale}
                  renderTextLayer={true}
                  renderAnnotationLayer={true}
                  onLoadSuccess={(page) => onPageLoadSuccess(page, pageNum)}
                  loading={<div className={styles.pageLoading}>加载中...</div>}
                  error={<div className={styles.pageError}>页面加载失败</div>}
                />
                {dims && (
                  <HighlightLayer
                    highlights={pageHighlights}
                    pageNumber={pageNum}
                    scale={scale}
                    pageWidth={dims.width}
                    pageHeight={dims.height}
                    activeHighlight={activeHighlight}
                    onHighlightClick={onHighlightClick}
                  />
                )}
              </>
            ) : (
              <div
                className={styles.pagePlaceholder}
                style={{
                  height: pageHeight,
                  background: 'var(--bg-tertiary, #f5f5f5)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--text-secondary, #999)',
                  fontSize: '14px',
                }}
              >
                第 {pageNum} 页
              </div>
            )}
          </div>
        );
      })}
    </div>
  );

  return viewMode === 'single' ? renderSinglePage() : renderScrollPages();
};

export default PDFPageRenderer;

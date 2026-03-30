import { useState, useCallback, useEffect, useRef } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import styles from './PDFReader.module.css';
import HighlightLayer from '../HighlightLayer/HighlightLayer';
import HighlightToolbar from '../HighlightToolbar/HighlightToolbar';
import ReadingAssist from '../ReadingAssist/ReadingAssist';

// 设置 PDF.js worker - 使用 unpkg CDN
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const PDFReader = ({
  file,
  onTextSelected,
  onPageChange,
  onCreateHighlight,
  onHighlightClick,
  onAddNote,
  initialPage = 1,
  highlights = [],
  activeHighlight = null,
  paperId = null,
}) => {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(initialPage);
  const [scale, setScale] = useState(1.0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('single'); // 'single' | 'scroll'
  const [toolbarVisible, setToolbarVisible] = useState(false);
  const [toolbarPosition, setToolbarPosition] = useState({ x: 0, y: 0 });
  const [selectedText, setSelectedText] = useState('');
  const [selectionRects, setSelectionRects] = useState([]);
  const [selectionPage, setSelectionPage] = useState(null);
  const [pageDimensions, setPageDimensions] = useState({}); // 存储每页的原始尺寸
  
  // 阅读辅助面板状态
  const [readingAssistVisible, setReadingAssistVisible] = useState(false);
  const [readingAssistType, setReadingAssistType] = useState(null); // 'explain' | 'summarize' | 'translate'
  const [readingAssistContent, setReadingAssistContent] = useState('');
  const [readingAssistTerm, setReadingAssistTerm] = useState('');
  const [readingAssistPosition, setReadingAssistPosition] = useState({ x: 0, y: 0 });
  
  const containerRef = useRef(null);
  const pageRefs = useRef({});

  // 文档加载成功
  const onDocumentLoadSuccess = useCallback(({ numPages }) => {
    setNumPages(numPages);
    setIsLoading(false);
    setError(null);
    // 重置页面尺寸缓存
    setPageDimensions({});
  }, []);

  // 文档加载失败
  const onDocumentLoadError = useCallback((err) => {
    console.error('PDF 加载失败:', err);
    setError('PDF 文件加载失败，请检查文件格式');
    setIsLoading(false);
  }, []);

  // 获取文件源
  const getFileSource = useCallback(() => {
    if (file instanceof File) {
      return URL.createObjectURL(file);
    }
    if (typeof file === 'string') {
      return file;
    }
    return null;
  }, [file]);

  // 页面切换
  const goToPage = useCallback((page) => {
    const newPage = Math.max(1, Math.min(page, numPages || 1));
    setPageNumber(newPage);
    onPageChange?.(newPage);
    
    // 滚动到对应页面
    if (viewMode === 'scroll' && pageRefs.current[newPage]) {
      pageRefs.current[newPage].scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [numPages, onPageChange, viewMode]);

  const goToPrevPage = useCallback(() => {
    goToPage(pageNumber - 1);
  }, [goToPage, pageNumber]);

  const goToNextPage = useCallback(() => {
    goToPage(pageNumber + 1);
  }, [goToPage, pageNumber]);

  // 缩放控制
  const zoomIn = useCallback(() => {
    setScale(prev => Math.min(prev + 0.25, 3.0));
  }, []);

  const zoomOut = useCallback(() => {
    setScale(prev => Math.max(prev - 0.25, 0.5));
  }, []);

  const fitToWidth = useCallback(() => {
    if (containerRef.current) {
      const containerWidth = containerRef.current.clientWidth - 48; // 减去 padding
      // 假设标准 PDF 页面宽度为 612pt (Letter) 或 595pt (A4)
      const standardPageWidth = 595;
      const newScale = containerWidth / standardPageWidth;
      setScale(Math.max(0.5, Math.min(newScale, 3.0)));
    }
  }, []);

  // 键盘快捷键
  useEffect(() => {
    const handleKeyDown = (e) => {
      // 避免在输入框中触发
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
      }

      switch (e.key) {
        case 'ArrowLeft':
        case 'ArrowUp':
          e.preventDefault();
          goToPrevPage();
          break;
        case 'ArrowRight':
        case 'ArrowDown':
        case ' ':
          e.preventDefault();
          goToNextPage();
          break;
        case 'Home':
          e.preventDefault();
          goToPage(1);
          break;
        case 'End':
          e.preventDefault();
          goToPage(numPages);
          break;
        default:
          break;
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [goToPage, goToPrevPage, goToNextPage, numPages]);

  // 页面加载成功，保存页面尺寸
  const handlePageLoadSuccess = useCallback((page, pageNum) => {
    setPageDimensions(prev => ({
      ...prev,
      [pageNum]: {
        width: page.originalWidth,
        height: page.originalHeight,
      }
    }));
  }, []);

  // 获取选中文本的 PDF 坐标
  const getSelectionRectsInPDF = useCallback((pageElement, pageNum) => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return null;
    
    const range = selection.getRangeAt(0);
    const rects = range.getClientRects();
    const pageRect = pageElement.getBoundingClientRect();
    const dims = pageDimensions[pageNum];
    
    if (!dims) return null;
    
    // 将页面像素坐标转换回 PDF 坐标
    // PDF 坐标系：左下角为原点，y 轴向上
    // 页面坐标系：左上角为原点，y 轴向下
    const pdfRects = Array.from(rects).map(rect => ({
      x0: (rect.left - pageRect.left) / scale,
      y0: dims.height - (rect.bottom - pageRect.top) / scale,  // 翻转 y 轴
      x1: (rect.right - pageRect.left) / scale,
      y1: dims.height - (rect.top - pageRect.top) / scale,     // 翻转 y 轴
    }));
    
    return pdfRects;
  }, [scale, pageDimensions]);

  // 文本选中处理
  const handleMouseUp = useCallback((e, pageNum) => {
    const selection = window.getSelection();
    const text = selection.toString().trim();
    
    if (!text) {
      setToolbarVisible(false);
      return;
    }
    
    // 获取选区位置以显示工具栏
    const range = selection.getRangeAt(0);
    const rects = range.getClientRects();
    if (rects.length > 0) {
      const lastRect = rects[rects.length - 1];
      setToolbarPosition({
        x: lastRect.left + lastRect.width / 2,
        y: lastRect.top
      });
      setToolbarVisible(true);
    }
    
    setSelectedText(text);
    setSelectionPage(pageNum);
    
    // 计算 PDF 坐标
    const pageElement = pageRefs.current[pageNum];
    if (pageElement) {
      const pdfRects = getSelectionRectsInPDF(pageElement, pageNum);
      setSelectionRects(pdfRects || []);
    }
    
    // 回调通知父组件
    if (onTextSelected) {
      const clientRects = Array.from(rects).map(rect => ({
        left: rect.left,
        top: rect.top,
        width: rect.width,
        height: rect.height,
        right: rect.right,
        bottom: rect.bottom
      }));
      onTextSelected(text, clientRects, pageNum);
    }
  }, [onTextSelected, getSelectionRectsInPDF]);

  // 处理创建高亮
  const handleCreateHighlight = useCallback((color, type) => {
    if (!selectedText || !selectionPage || selectionRects.length === 0 || !paperId) {
      return;
    }
    
    const highlightData = {
      paper_id: paperId,
      page: selectionPage,
      rects: JSON.stringify(selectionRects),
      color: color,
      highlight_type: type,
      selected_text: selectedText
    };
    
    onCreateHighlight?.(highlightData);
    
    // 清除选区
    window.getSelection().removeAllRanges();
    setToolbarVisible(false);
    setSelectedText('');
    setSelectionRects([]);
    setSelectionPage(null);
  }, [selectedText, selectionPage, selectionRects, paperId, onCreateHighlight]);

  // 关闭工具栏
  const handleCloseToolbar = useCallback(() => {
    setToolbarVisible(false);
    window.getSelection().removeAllRanges();
  }, []);

  // 处理术语解释
  const handleExplain = useCallback((text) => {
    setReadingAssistType('explain');
    setReadingAssistContent(text);
    setReadingAssistTerm(text);
    setReadingAssistPosition(toolbarPosition);
    setReadingAssistVisible(true);
    window.getSelection().removeAllRanges();
  }, [toolbarPosition]);

  // 处理文本摘要
  const handleSummarize = useCallback((text) => {
    setReadingAssistType('summarize');
    setReadingAssistContent(text);
    setReadingAssistTerm('');
    setReadingAssistPosition(toolbarPosition);
    setReadingAssistVisible(true);
    window.getSelection().removeAllRanges();
  }, [toolbarPosition]);

  // 处理翻译
  const handleTranslate = useCallback((text) => {
    setReadingAssistType('translate');
    setReadingAssistContent(text);
    setReadingAssistTerm('');
    setReadingAssistPosition(toolbarPosition);
    setReadingAssistVisible(true);
    window.getSelection().removeAllRanges();
  }, [toolbarPosition]);

  // 关闭阅读辅助面板
  const handleCloseReadingAssist = useCallback(() => {
    setReadingAssistVisible(false);
    setReadingAssistType(null);
    setReadingAssistContent('');
    setReadingAssistTerm('');
  }, []);

  // 页码输入处理
  const handlePageInputChange = useCallback((e) => {
    const value = parseInt(e.target.value, 10);
    if (!isNaN(value)) {
      goToPage(value);
    }
  }, [goToPage]);

  // 获取指定页面的高亮
  const getHighlightsForPage = useCallback((pageNum) => {
    return highlights.filter(h => h.page === pageNum);
  }, [highlights]);

  // 渲染页面
  const renderPages = () => {
    if (viewMode === 'single') {
      const pageHighlights = getHighlightsForPage(pageNumber);
      const dims = pageDimensions[pageNumber];
      
      return (
        <div 
          ref={(el) => { pageRefs.current[pageNumber] = el; }}
          className={styles.pageWrapper} 
          data-page-number={pageNumber}
          onMouseUp={(e) => handleMouseUp(e, pageNumber)}
        >
          <Page
            pageNumber={pageNumber}
            scale={scale}
            renderTextLayer={true}
            renderAnnotationLayer={true}
            onLoadSuccess={(page) => handlePageLoadSuccess(page, pageNumber)}
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
    }

    // 滚动模式 - 渲染所有页面
    return Array.from({ length: numPages || 0 }, (_, i) => i + 1).map((pageNum) => {
      const pageHighlights = getHighlightsForPage(pageNum);
      const dims = pageDimensions[pageNum];
      
      return (
        <div
          key={pageNum}
          ref={(el) => { pageRefs.current[pageNum] = el; }}
          className={styles.pageWrapper}
          data-page-number={pageNum}
          onMouseUp={(e) => handleMouseUp(e, pageNum)}
        >
          <Page
            pageNumber={pageNum}
            scale={scale}
            renderTextLayer={true}
            renderAnnotationLayer={true}
            onLoadSuccess={(page) => handlePageLoadSuccess(page, pageNum)}
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
        </div>
      );
    });
  };

  const fileSource = getFileSource();

  if (!fileSource) {
    return (
      <div className={styles.container}>
        <div className={styles.error}>无效的 PDF 文件</div>
      </div>
    );
  }

  return (
    <div className={styles.container} ref={containerRef}>
      {/* 高亮工具栏 */}
      <HighlightToolbar
        position={toolbarPosition}
        visible={toolbarVisible}
        selectedText={selectedText}
        onCreateHighlight={handleCreateHighlight}
        onAddNote={onAddNote}
        onExplain={handleExplain}
        onSummarize={handleSummarize}
        onTranslate={handleTranslate}
        onClose={handleCloseToolbar}
      />

      {/* 阅读辅助面板 */}
      <ReadingAssist
        type={readingAssistType}
        content={readingAssistContent}
        term={readingAssistTerm}
        position={readingAssistPosition}
        visible={readingAssistVisible}
        onClose={handleCloseReadingAssist}
      />
      
      {/* 工具栏 */}
      <div className={styles.toolbar}>
        <div className={styles.toolbarGroup}>
          {/* 页码控制 */}
          <button
            className={styles.toolbarBtn}
            onClick={goToPrevPage}
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
              onChange={handlePageInputChange}
              className={styles.pageInput}
            />
            <span className={styles.pageTotal}> / {numPages || '-'}</span>
          </div>
          
          <button
            className={styles.toolbarBtn}
            onClick={goToNextPage}
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
            onClick={zoomOut}
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
            onClick={zoomIn}
            disabled={scale >= 3.0}
            title="放大"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z" />
            </svg>
          </button>
          
          <button
            className={styles.toolbarBtn}
            onClick={fitToWidth}
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
            onClick={() => setViewMode('single')}
            title="单页模式"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M4 4h16v16H4z" fill="none" stroke="currentColor" strokeWidth="2"/>
              <path d="M6 6h12v12H6z" />
            </svg>
          </button>
          <button
            className={`${styles.toolbarBtn} ${viewMode === 'scroll' ? styles.active : ''}`}
            onClick={() => setViewMode('scroll')}
            title="滚动模式"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M4 4h16v6H4zm0 8h16v6H4z" fill="none" stroke="currentColor" strokeWidth="2"/>
              <path d="M6 6h12v2H6zm0 8h12v2H6z" />
            </svg>
          </button>
        </div>
      </div>

      {/* PDF 内容区域 */}
      <div className={styles.pdfContent}>
        {isLoading && (
          <div className={styles.loading}>
            <div className={styles.spinner} />
            <span>正在加载 PDF...</span>
          </div>
        )}
        
        {error && (
          <div className={styles.error}>
            <svg viewBox="0 0 24 24" width="48" height="48" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
            </svg>
            <span>{error}</span>
          </div>
        )}

        <Document
          file={fileSource}
          onLoadSuccess={onDocumentLoadSuccess}
          onLoadError={onDocumentLoadError}
          loading={null}
          className={styles.document}
        >
          {!isLoading && !error && renderPages()}
        </Document>
      </div>
    </div>
  );
};

export default PDFReader;

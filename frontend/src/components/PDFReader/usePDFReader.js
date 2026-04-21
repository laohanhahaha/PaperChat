import { useState, useCallback, useEffect, useRef } from 'react';

/**
 * usePDFReader - PDFReader 状态逻辑 Hook
 * 封装所有非渲染逻辑：页面导航、缩放、文本选中、高亮、阅读辅助面板
 */
export function usePDFReader({
  initialPage = 1,
  highlights = [],
  activeHighlight = null,
  paperId = null,
  onTextSelected,
  onCreateHighlight: onCreateHighlightProp,
}) {
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
  const [pageDimensions, setPageDimensions] = useState({});
  const [visiblePages, setVisiblePages] = useState(new Set([1, 2, 3]));

  // 阅读辅助面板状态
  const [readingAssistVisible, setReadingAssistVisible] = useState(false);
  const [readingAssistType, setReadingAssistType] = useState(null);
  const [readingAssistContent, setReadingAssistContent] = useState('');
  const [readingAssistTerm, setReadingAssistTerm] = useState('');
  const [readingAssistPosition, setReadingAssistPosition] = useState({ x: 0, y: 0 });

  const containerRef = useRef(null);
  const pageRefs = useRef({});
  const scrollContainerRef = useRef(null);
  const observerRef = useRef(null);

  // ---------- 文档加载 ----------
  const onDocumentLoadSuccess = useCallback(({ numPages: n }) => {
    setNumPages(n);
    setIsLoading(false);
    setError(null);
    setPageDimensions({});
    setVisiblePages(new Set([1, 2, 3].filter(p => p <= n)));
  }, []);

  const onDocumentLoadError = useCallback((err) => {
    console.error('PDF 加载失败:', err);
    setError('PDF 文件加载失败，请检查文件格式');
    setIsLoading(false);
  }, []);

  // ---------- 页面导航 ----------
  const goToPage = useCallback((page) => {
    const newPage = Math.max(1, Math.min(page, numPages || 1));
    setPageNumber(newPage);
    if (viewMode === 'scroll' && pageRefs.current[newPage]) {
      pageRefs.current[newPage].scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [numPages, viewMode]);

  const goToPrevPage = useCallback(() => goToPage(pageNumber - 1), [goToPage, pageNumber]);
  const goToNextPage = useCallback(() => goToPage(pageNumber + 1), [goToPage, pageNumber]);

  const handlePageInputChange = useCallback((e) => {
    const value = parseInt(e.target.value, 10);
    if (!isNaN(value)) goToPage(value);
  }, [goToPage]);

  // ---------- 缩放控制 ----------
  const zoomIn = useCallback(() => setScale(prev => Math.min(prev + 0.25, 3.0)), []);
  const zoomOut = useCallback(() => setScale(prev => Math.max(prev - 0.25, 0.5)), []);

  const fitToWidth = useCallback(() => {
    if (containerRef.current) {
      const containerWidth = containerRef.current.clientWidth - 48;
      const standardPageWidth = 595;
      const newScale = containerWidth / standardPageWidth;
      setScale(Math.max(0.5, Math.min(newScale, 3.0)));
    }
  }, []);

  // ---------- 键盘快捷键 ----------
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
      switch (e.key) {
        case 'ArrowLeft': case 'ArrowUp':
          e.preventDefault(); goToPrevPage(); break;
        case 'ArrowRight': case 'ArrowDown': case ' ':
          e.preventDefault(); goToNextPage(); break;
        case 'Home':
          e.preventDefault(); goToPage(1); break;
        case 'End':
          e.preventDefault(); goToPage(numPages); break;
        default: break;
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [goToPage, goToPrevPage, goToNextPage, numPages]);

  // ---------- 页面尺寸缓存 ----------
  const handlePageLoadSuccess = useCallback((page, pageNum) => {
    setPageDimensions(prev => ({
      ...prev,
      [pageNum]: { width: page.originalWidth, height: page.originalHeight },
    }));
  }, []);

  // ---------- 文本选中处理 ----------
  const getSelectionRectsInPDF = useCallback((pageElement, pageNum) => {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed) return null;
    const range = selection.getRangeAt(0);
    const rects = range.getClientRects();
    const pageRect = pageElement.getBoundingClientRect();
    const dims = pageDimensions[pageNum];
    if (!dims) return null;
    return Array.from(rects).map(rect => ({
      x0: (rect.left - pageRect.left) / scale,
      y0: dims.height - (rect.bottom - pageRect.top) / scale,
      x1: (rect.right - pageRect.left) / scale,
      y1: dims.height - (rect.top - pageRect.top) / scale,
    }));
  }, [scale, pageDimensions]);

  const handleMouseUp = useCallback((e, pageNum) => {
    const selection = window.getSelection();
    const text = selection.toString().trim();
    if (!text) {
      setToolbarVisible(false);
      return;
    }
    if (readingAssistVisible) {
      setReadingAssistVisible(false);
      setReadingAssistType(null);
      setReadingAssistContent('');
      setReadingAssistTerm('');
    }
    const range = selection.getRangeAt(0);
    const rects = range.getClientRects();
    if (rects.length > 0) {
      const lastRect = rects[rects.length - 1];
      setToolbarPosition({ x: lastRect.left + lastRect.width / 2, y: lastRect.top });
      setToolbarVisible(true);
    }
    setSelectedText(text);
    setSelectionPage(pageNum);
    const pageElement = pageRefs.current[pageNum];
    if (pageElement) {
      const pdfRects = getSelectionRectsInPDF(pageElement, pageNum);
      setSelectionRects(pdfRects || []);
    }
    if (onTextSelected) {
      const clientRects = Array.from(rects).map(rect => ({
        left: rect.left, top: rect.top, width: rect.width, height: rect.height,
        right: rect.right, bottom: rect.bottom,
      }));
      onTextSelected(text, clientRects, pageNum);
    }
  }, [onTextSelected, getSelectionRectsInPDF, readingAssistVisible]);

  // ---------- 高亮操作 ----------
  const handleCreateHighlight = useCallback((color, type) => {
    if (!selectedText || !selectionPage || selectionRects.length === 0 || !paperId) return;
    const highlightData = {
      paper_id: paperId,
      page: selectionPage,
      rects: JSON.stringify(selectionRects),
      color,
      highlight_type: type,
      selected_text: selectedText,
    };
    onCreateHighlightProp?.(highlightData);
    window.getSelection().removeAllRanges();
    setToolbarVisible(false);
    setSelectedText('');
    setSelectionRects([]);
    setSelectionPage(null);
  }, [selectedText, selectionPage, selectionRects, paperId, onCreateHighlightProp]);

  const handleCloseToolbar = useCallback(() => {
    setToolbarVisible(false);
    window.getSelection().removeAllRanges();
  }, []);

  // ---------- 阅读辅助面板 ----------
  const handleExplain = useCallback((text) => {
    setReadingAssistType('explain');
    setReadingAssistContent(text);
    setReadingAssistTerm(text);
    setReadingAssistPosition(toolbarPosition);
    setReadingAssistVisible(true);
    window.getSelection().removeAllRanges();
  }, [toolbarPosition]);

  const handleSummarize = useCallback((text) => {
    setReadingAssistType('summarize');
    setReadingAssistContent(text);
    setReadingAssistTerm('');
    setReadingAssistPosition(toolbarPosition);
    setReadingAssistVisible(true);
    window.getSelection().removeAllRanges();
  }, [toolbarPosition]);

  const handleTranslate = useCallback((text) => {
    setReadingAssistType('translate');
    setReadingAssistContent(text);
    setReadingAssistTerm('');
    setReadingAssistPosition(toolbarPosition);
    setReadingAssistVisible(true);
    window.getSelection().removeAllRanges();
  }, [toolbarPosition]);

  const handleCloseReadingAssist = useCallback(() => {
    setReadingAssistVisible(false);
    setReadingAssistType(null);
    setReadingAssistContent('');
    setReadingAssistTerm('');
  }, []);

  // ---------- IntersectionObserver 懒加载（滚动模式，滑动窗口机制） ----------
  useEffect(() => {
    if (viewMode !== 'scroll' || !numPages) return;
    if (observerRef.current) observerRef.current.disconnect();
    observerRef.current = new IntersectionObserver(
      (entries) => {
        setVisiblePages((prev) => {
          const next = new Set(prev);
          entries.forEach((entry) => {
            const pageNum = parseInt(entry.target.dataset.page, 10);
            if (entry.isIntersecting) {
              // 进入视口：加载该页及前后各 2 页缓冲区
              for (let p = Math.max(1, pageNum - 2); p <= Math.min(numPages, pageNum + 2); p++) {
                next.add(p);
              }
            } else {
              // 离开视口（rootMargin 外）：移除该页，缓冲区由 rootMargin 控制
              next.delete(pageNum);
            }
          });
          return next;
        });
      },
      // rootMargin '150% 0px' 意味着进入/离开 1.5 倍视口高度范围时才触发
      { root: scrollContainerRef.current, rootMargin: '150% 0px', threshold: 0 }
    );
    Object.values(pageRefs.current).forEach((el) => {
      if (el && observerRef.current) observerRef.current.observe(el);
    });
    return () => observerRef.current?.disconnect();
  }, [viewMode, numPages]);

  const registerPageElement = useCallback((el, pageNum) => {
    if (el) {
      pageRefs.current[pageNum] = el;
      if (observerRef.current && viewMode === 'scroll') {
        observerRef.current.observe(el);
      }
    }
  }, [viewMode]);

  const getHighlightsForPage = useCallback((pageNum) => {
    return highlights.filter(h => h.page === pageNum);
  }, [highlights]);

  return {
    // 状态
    numPages, pageNumber, scale, isLoading, error,
    viewMode, setViewMode,
    toolbarVisible, toolbarPosition, selectedText, selectionRects, selectionPage,
    pageDimensions, visiblePages,
    readingAssistVisible, readingAssistType, readingAssistContent,
    readingAssistTerm, readingAssistPosition,
    // refs
    containerRef, pageRefs, scrollContainerRef,
    // 文档加载
    onDocumentLoadSuccess, onDocumentLoadError,
    // 导航
    goToPage, goToPrevPage, goToNextPage, handlePageInputChange,
    // 缩放
    zoomIn, zoomOut, fitToWidth,
    // 文本选中
    handleMouseUp,
    // 高亮
    handleCreateHighlight, handleCloseToolbar,
    // 阅读辅助
    handleExplain, handleSummarize, handleTranslate, handleCloseReadingAssist,
    // 页面
    handlePageLoadSuccess, registerPageElement, getHighlightsForPage,
  };
}

import { useEffect, useRef, useState } from 'react';
import * as pdfjsLib from 'pdfjs-dist';
import styles from './PDFViewer.module.css';

// 配置 PDF.js worker
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.mjs',
  import.meta.url
).toString();

const PDFViewer = ({ file, pdfData, currentPage, onCanvasReady, children }) => {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const [pdfDoc, setPdfDoc] = useState(null);
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0, scale: 1 });
  const [totalPages, setTotalPages] = useState(0);

  // 加载PDF文档
  useEffect(() => {
    if (!file) return;

    const loadPDF = async () => {
      const arrayBuffer = await file.arrayBuffer();
      const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
      setPdfDoc(pdf);
      setTotalPages(pdf.numPages);
    };

    loadPDF();
  }, [file]);

  // 渲染当前页
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return;

    const renderPage = async () => {
      const page = await pdfDoc.getPage(currentPage + 1); // PDF.js页码从1开始
      const viewport = page.getViewport({ scale: 1.5 }); // 基础缩放1.5倍保证清晰度
      
      const canvas = canvasRef.current;
      const context = canvas.getContext('2d');
      
      // 设备像素比适配
      const dpr = window.devicePixelRatio || 1;
      canvas.width = viewport.width * dpr;
      canvas.height = viewport.height * dpr;
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      context.scale(dpr, dpr);

      await page.render({
        canvasContext: context,
        viewport: viewport,
      }).promise;

      // 计算缩放比例：CSS显示尺寸 / PDF原始页面尺寸
      const pdfPageWidth = pdfData?.page_width || page.getViewport({ scale: 1 }).width;
      const pdfPageHeight = pdfData?.page_height || page.getViewport({ scale: 1 }).height;
      const scaleX = viewport.width / pdfPageWidth;
      const scaleY = viewport.height / pdfPageHeight;

      const newCanvasSize = {
        width: viewport.width,
        height: viewport.height,
        scale: scaleX, // X和Y缩放比例应一致
        pdfWidth: pdfPageWidth,
        pdfHeight: pdfPageHeight,
      };
      
      setCanvasSize(newCanvasSize);
      onCanvasReady?.(newCanvasSize);
    };

    renderPage();
  }, [pdfDoc, currentPage, pdfData, onCanvasReady]);

  return (
    <div className={styles.viewerContainer} ref={containerRef}>
      <div className={styles.canvasWrapper}>
        <canvas ref={canvasRef} className={styles.pdfCanvas} />
        {/* children slot 用于渲染悬浮层 */}
        {children && typeof children === 'function' 
          ? children({ canvasSize, currentPage }) 
          : children}
      </div>
    </div>
  );
};

export default PDFViewer;

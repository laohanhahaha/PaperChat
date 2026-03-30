import styles from './HighlightLayer.module.css';

/**
 * 高亮层组件
 * 在 react-pdf 的每个 Page 上叠加一个绝对定位的层来渲染高亮区域
 * 
 * Props:
 * - highlights: array of highlight objects for THIS page
 * - pageNumber: number
 * - scale: number (当前缩放比例)
 * - pageWidth: number (PDF 页面原始宽度)
 * - pageHeight: number (PDF 页面原始高度)
 * - activeHighlight: object | null (当前选中的高亮)
 * - onHighlightClick: (highlight) => void
 */
function HighlightLayer({ 
  highlights, 
  scale, 
  pageWidth, 
  pageHeight, 
  activeHighlight,
  onHighlightClick 
}) {
  // 将 PDF 坐标转换为页面像素坐标
  // PDF 坐标系：左下角为原点，y 轴向上
  // 页面坐标系：左上角为原点，y 轴向下
  const transformRect = (rect) => {
    return {
      left: rect.x0 * scale,
      top: (pageHeight - rect.y1) * scale,   // 翻转 y 轴
      width: (rect.x1 - rect.x0) * scale,
      height: (rect.y1 - rect.y0) * scale,
    };
  };

  // 获取高亮样式
  const getHighlightStyle = (highlight) => {
    const isActive = activeHighlight?.id === highlight.id;
    const baseStyle = {
      backgroundColor: highlight.color,
      opacity: isActive ? 0.5 : 0.35,
    };

    // 根据高亮类型返回不同样式
    switch (highlight.highlight_type) {
      case 'underline':
        return {
          ...baseStyle,
          backgroundColor: 'transparent',
          borderBottom: `3px solid ${highlight.color}`,
          opacity: isActive ? 0.8 : 0.6,
        };
      case 'strikethrough':
        return {
          ...baseStyle,
          backgroundColor: 'transparent',
          textDecoration: 'line-through',
          textDecorationColor: highlight.color,
          textDecorationThickness: '2px',
          opacity: isActive ? 0.8 : 0.6,
        };
      case 'highlight':
      default:
        return baseStyle;
    }
  };

  if (!highlights || highlights.length === 0 || !pageWidth || !pageHeight) {
    return null;
  }

  return (
    <div 
      className={styles.highlightLayer}
      style={{
        width: pageWidth * scale,
        height: pageHeight * scale,
      }}
    >
      {highlights.map(highlight => {
        let rects;
        try {
          rects = JSON.parse(highlight.rects);
        } catch (e) {
          console.error('解析高亮区域失败:', e);
          return null;
        }
        
        return rects.map((rect, i) => {
          const pos = transformRect(rect);
          const isActive = activeHighlight?.id === highlight.id;
          
          return (
            <div
              key={`${highlight.id}-${i}`}
              className={`${styles.highlight} ${isActive ? styles.active : ''}`}
              style={{
                position: 'absolute',
                left: pos.left,
                top: pos.top,
                width: pos.width,
                height: pos.height,
                ...getHighlightStyle(highlight),
              }}
              onClick={(e) => {
                e.stopPropagation();
                onHighlightClick?.(highlight);
              }}
              title={highlight.selected_text?.substring(0, 100)}
            />
          );
        });
      })}
    </div>
  );
}

export default HighlightLayer;

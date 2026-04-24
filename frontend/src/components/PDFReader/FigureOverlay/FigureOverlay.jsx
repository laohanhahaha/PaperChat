import styles from './FigureOverlay.module.css';

/**
 * FigureOverlay — 在 PDF 页面上叠加图表区域标记
 *
 * props:
 *   figures: [{bbox: [x0,y0,x1,y1], type: "figure"|"table", label: string, index: number}]
 *   pageWidth: number — 页面渲染宽度（用于坐标转换）
 *   pageHeight: number — 页面渲染高度
 *   originalWidth: number — PDF 原始宽度（用于 bbox 比例缩放）
 *   originalHeight: number — PDF 原始高度
 *   onFigureClick: (figure) => void
 *   onFigureHover: (figure) => void
 *
 * 性能: 纯 CSS 渲染，无性能影响
 */
const FigureOverlay = ({
  figures,
  pageWidth,
  pageHeight,
  originalWidth,
  originalHeight,
  onFigureClick,
  onFigureHover,
}) => {
  if (!figures?.length) return null;

  const scaleX = pageWidth / originalWidth;
  const scaleY = pageHeight / originalHeight;

  return (
    <div className={styles.overlay}>
      {figures.map((fig, idx) => {
        const [x0, y0, x1, y1] = fig.bbox;
        return (
          <div
            key={idx}
            className={`${styles.figureBox} ${styles[fig.type]}`}
            style={{
              left: x0 * scaleX,
              top: y0 * scaleY,
              width: (x1 - x0) * scaleX,
              height: (y1 - y0) * scaleY,
            }}
            onClick={() => onFigureClick?.(fig)}
            onMouseEnter={() => onFigureHover?.(fig)}
            onMouseLeave={() => onFigureHover?.(null)}
          >
            <span className={styles.label}>{fig.label}</span>
          </div>
        );
      })}
    </div>
  );
};

export default FigureOverlay;

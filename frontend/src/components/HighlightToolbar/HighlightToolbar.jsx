import { useRef, useEffect } from 'react';
import styles from './HighlightToolbar.module.css';

// 预设高亮配色
const HIGHLIGHT_COLORS = [
  { name: '黄色', color: '#FFEB3B' },
  { name: '绿色', color: '#4CAF50' },
  { name: '蓝色', color: '#2196F3' },
  { name: '红色', color: '#F44336' },
];

/**
 * 高亮工具栏组件
 * 当用户在 PDF 上选中文本后，在选中区域上方弹出一个浮动工具栏
 * 
 * Props:
 * - position: { x, y } 工具栏位置（相对于视口）
 * - selectedText: string 选中的文本内容
 * - onCreateHighlight: (color, type) => void
 * - onAddNote: () => void 添加笔记回调
 * - onExplain: (text) => void 解释术语回调
 * - onSummarize: (text) => void 摘要回调
 * - onTranslate: (text) => void 翻译回调
 * - onSaveToKnowledge: (text) => void 保存到知识库回调
 * - onClose: () => void
 * - visible: boolean
 */
function HighlightToolbar({ 
  position, 
  selectedText,
  onCreateHighlight, 
  onAddNote,
  onExplain,
  onSummarize,
  onTranslate,
  onSaveToKnowledge,
  onClose, 
  visible 
}) {
  // 判断选中文本长度，决定显示哪些按钮
  const textLength = selectedText?.length || 0;
  const isShortText = textLength > 0 && textLength <= 30; // 短文本（术语/短语）
  const isLongText = textLength > 30; // 长文本
  const toolbarRef = useRef(null);

  // 点击外部关闭工具栏
  useEffect(() => {
    if (!visible) return;

    const handleClickOutside = (e) => {
      if (toolbarRef.current && !toolbarRef.current.contains(e.target)) {
        onClose?.();
      }
    };

    // 延迟添加事件监听，避免立即触发
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 100);

    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [visible, onClose]);

  // 处理颜色选择
  const handleColorClick = (color) => {
    onCreateHighlight?.(color, 'highlight');
    onClose?.();
  };

  if (!visible) return null;

  // 计算工具栏位置，确保不超出视口
  const toolbarWidth = 180; // 预估工具栏宽度
  const toolbarHeight = 50; // 预估工具栏高度
  
  let left = position.x - toolbarWidth / 2;
  let top = position.y - toolbarHeight - 10; // 在选中文本上方

  // 边界检查
  if (left < 10) left = 10;
  if (left + toolbarWidth > window.innerWidth - 10) {
    left = window.innerWidth - toolbarWidth - 10;
  }
  if (top < 10) {
    top = position.y + 20; // 如果上方空间不足，显示在下方
  }

  return (
    <div
      ref={toolbarRef}
      className={styles.toolbar}
      style={{
        left: `${left}px`,
        top: `${top}px`,
      }}
    >
      <div className={styles.colorList}>
        {HIGHLIGHT_COLORS.map((item) => (
          <button
            key={item.color}
            className={styles.colorBtn}
            style={{ backgroundColor: item.color }}
            onClick={() => handleColorClick(item.color)}
            title={`高亮 - ${item.name}`}
          />
        ))}
      </div>
      <div className={styles.divider} />
      <button
        className={styles.actionBtn}
        onClick={() => {
          onSaveToKnowledge?.(selectedText);
          onClose?.();
        }}
        title="保存为知识卡片"
      >
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
        </svg>
      </button>
      <button
        className={styles.actionBtn}
        onClick={() => {
          onCreateHighlight?.('#FFEB3B', 'underline');
          onClose?.();
        }}
        title="下划线"
      >
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M5 21h14v-2H5v2zm7-4a6 6 0 0 0 6-6V3h-2.5v8a3.5 3.5 0 0 1-7 0V3H6v8a6 6 0 0 0 6 6z"/>
        </svg>
      </button>
      <div className={styles.divider} />
      <button
        className={styles.actionBtn}
        onClick={() => {
          onAddNote?.();
          onClose?.();
        }}
        title="添加笔记"
      >
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
        </svg>
      </button>
      <button
        className={styles.actionBtn}
        onClick={onClose}
        title="取消"
      >
        <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
          <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
        </svg>
      </button>

      <div className={styles.divider} />

      {/* 阅读辅助功能按钮 */}
      {isShortText && (
        <button
          className={styles.actionBtn}
          onClick={() => {
            onExplain?.(selectedText);
            onClose?.();
          }}
          title="解释术语"
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z"/>
          </svg>
        </button>
      )}

      {isLongText && (
        <>
          <button
            className={styles.actionBtn}
            onClick={() => {
              onSummarize?.(selectedText);
              onClose?.();
            }}
            title="生成摘要"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z"/>
            </svg>
          </button>
          <button
            className={styles.actionBtn}
            onClick={() => {
              onTranslate?.(selectedText);
              onClose?.();
            }}
            title="翻译"
          >
            <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
              <path d="M12.87 15.07l-2.54-2.51.03-.03c1.74-1.94 2.98-4.17 3.71-6.53H17V4h-7V2H8v2H1v1.99h11.17C11.5 7.92 10.44 9.75 9 11.35 8.07 10.32 7.3 9.19 6.69 8h-2c.73 1.63 1.73 3.17 2.98 4.56l-5.09 5.02L4 19l5-5 3.11 3.11.76-2.04zM18.5 10h-2L12 22h2l1.12-3h4.75L21 22h2l-4.5-12zm-2.62 7l1.62-4.33L19.12 17h-3.24z"/>
            </svg>
          </button>
        </>
      )}
    </div>
  );
}

export default HighlightToolbar;

import React, { useState } from 'react';

export default function SelectedPapersBar({
  selectedPaperIds,
  getPaperTitle,
  removePaperFromCrossDoc,
  onOpenSelector,
  styles,
  privatePaperIds = [],
  onTogglePrivacy,
}) {
  const [hoveredPid, setHoveredPid] = useState(null);

  return (
    <div className={styles.selectedPapersBar}>
      <div className={styles.selectedPapersContent}>
        {selectedPaperIds.length > 0 ? (
          <>
            {selectedPaperIds.map(pid => {
              const isPrivate = privatePaperIds.includes(pid);
              const isHovered = hoveredPid === pid;
              return (
                <div
                  key={pid}
                  className={styles.selectedPaperTag}
                  onMouseEnter={() => setHoveredPid(pid)}
                  onMouseLeave={() => setHoveredPid(null)}
                >
                  <span
                    style={{
                      cursor: 'pointer',
                      fontSize: '13px',
                      lineHeight: 1,
                      opacity: isPrivate ? 1 : (isHovered ? 0.7 : 0),
                      transition: 'opacity 0.15s',
                      userSelect: 'none',
                    }}
                    title={isPrivate ? '隐私保护中 — 点击取消' : '点击标记为隐私（强制本地处理）'}
                    onClick={(e) => {
                      e.stopPropagation();
                      onTogglePrivacy?.(pid, !isPrivate);
                    }}
                  >
                    {isPrivate ? '🔒' : '🔓'}
                  </span>
                  <span className={styles.selectedPaperTitle} title={getPaperTitle(pid)}>
                    {getPaperTitle(pid)}
                  </span>
                  <button
                    className={styles.selectedPaperRemove}
                    onClick={() => removePaperFromCrossDoc(pid)}
                    title="移除论文"
                  >
                    ×
                  </button>
                </div>
              );
            })}
            <button
              className={styles.addPaperChip}
              onClick={onOpenSelector}
              title="选择更多论文"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 5v14M5 12h14" />
              </svg>
              选择论文
            </button>
          </>
        ) : (
          <button
            className={styles.selectPaperPrompt}
            onClick={onOpenSelector}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
            </svg>
            <span>选择论文开始对话</span>
          </button>
        )}
      </div>
    </div>
  );
}

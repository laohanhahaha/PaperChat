import React from 'react';

export default function SessionSidebar({
  sessions,
  currentSessionId,
  editingSessionId,
  editingTitle,
  setEditingTitle,
  handleNewSession,
  handleSwitchSession,
  handleDeleteSession,
  handleStartEditing,
  handleSaveTitle,
  handleEditKeyDown,
  formatTime,
  styles,
}) {
  return (
    <aside className={styles.sidebar}>
      <button className={styles.newChatBtn} onClick={handleNewSession}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 5v14M5 12h14" />
        </svg>
        新对话
      </button>

      <div className={styles.historySection}>
        <div className={styles.sectionHeader}>
          <span>历史对话</span>
        </div>
        <div className={styles.historyList}>
          {sessions.map(session => (
            <div
              key={session.id}
              className={`${styles.historyItem} ${session.id === currentSessionId ? styles.historyItemActive : ''}`}
              onClick={() => handleSwitchSession(session.id)}
            >
              {editingSessionId === session.id ? (
                <input
                  type="text"
                  className={styles.titleEditInput}
                  value={editingTitle}
                  onChange={(e) => setEditingTitle(e.target.value)}
                  onKeyDown={handleEditKeyDown}
                  onBlur={handleSaveTitle}
                  autoFocus
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <div
                  className={styles.historyTitle}
                  onDoubleClick={(e) => handleStartEditing(e, session)}
                  title="双击重命名"
                >
                  {session.is_cross_doc && <span className={styles.crossBadge}>跨</span>}
                  {session.title}
                </div>
              )}
              <div className={styles.historyMeta}>{formatTime(session.updated_at)}</div>
              <button
                className={styles.historyDelete}
                onClick={(e) => handleDeleteSession(e, session.id)}
              >×</button>
            </div>
          ))}
          {sessions.length === 0 && (
            <div className={styles.emptyHint}>暂无对话记录</div>
          )}
        </div>
      </div>
    </aside>
  );
}

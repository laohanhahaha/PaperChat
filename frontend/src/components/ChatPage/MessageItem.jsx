import React, { memo, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import ToolResultCard from './ToolResultCard';
import ThinkingBlock from './ThinkingBlock';
import knowledgeApi from '../../api/knowledgeApi';

// 轻量 Toast 组件
function SaveToast({ visible, success }) {
  if (!visible) return null;
  return (
    <div style={{
      position: 'fixed',
      bottom: '24px',
      right: '24px',
      padding: '10px 18px',
      borderRadius: '8px',
      background: success ? '#1a7a4a' : '#8b1a1a',
      color: '#fff',
      fontSize: '13px',
      fontWeight: 500,
      zIndex: 9999,
      boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
      pointerEvents: 'none',
      transition: 'opacity 0.2s',
    }}>
      {success ? '✓ 已保存为知识卡片' : '✗ 保存失败，请重试'}
    </div>
  );
}

const MessageItem = memo(function MessageItem({ msg, isLast, isChatting, renderMarkdown, styles, paperId }) {
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState({ visible: false, success: false });

  const showToast = useCallback((success) => {
    setToast({ visible: true, success });
    setTimeout(() => setToast({ visible: false, success: false }), 2500);
  }, []);

  const handleSaveAsNote = useCallback(async (e) => {
    e.stopPropagation();
    if (saving || !msg.content) return;
    setSaving(true);
    try {
      await knowledgeApi.createFromChat(msg.content, paperId || null);
      showToast(true);
    } catch {
      showToast(false);
    } finally {
      setSaving(false);
    }
  }, [saving, msg.content, paperId, showToast]);

  return (
    <>
      <div
        className={`${styles.messageRow} ${msg.role === 'user' ? styles.messageUser : styles.messageAssistant}`}
      >
        {msg.role === 'assistant' && (
          <div className={styles.avatar}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 2a7 7 0 017 7v1a7 7 0 01-14 0V9a7 7 0 017-7zM5.5 21a8.38 8.38 0 0113 0" />
            </svg>
          </div>
        )}
        <div
          className={styles.messageBubble}
          style={{ position: 'relative' }}
        >
          {/* 深度思考块（如果有 thinkingContent） */}
          {msg.role === 'assistant' && msg.thinkingContent && (
            <ThinkingBlock
              content={msg.thinkingContent}
              isThinking={false}
            />
          )}
          {msg.content ? (
            msg.role === 'assistant' ? renderMarkdown(msg.content) : msg.content
          ) : (
            isChatting && isLast ? (
              <div className={styles.thinkingDots}>
                <span></span><span></span><span></span>
              </div>
            ) : ''
          )}
          {msg.role === 'assistant' && msg.toolResult && (
            <ToolResultCard toolResult={msg.toolResult} />
          )}
          {/* 转为文档编辑按钮（仅 assistant 且有内容时显示） */}
          {msg.role === 'assistant' && msg.content && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                sessionStorage.setItem('editor_draft_content', msg.content);
                navigate('/writing', { state: { tab: 'editor', content: msg.content } });
              }}
              title="转为文档编辑"
              className={styles.convertEditBtn}
              style={{
                position: 'absolute',
                bottom: '8px',
                right: '100px',
                padding: '4px 8px',
                border: 'none',
                borderRadius: '6px',
                background: 'transparent',
                cursor: 'pointer',
                opacity: 0,
                transition: 'opacity 0.15s, background 0.15s',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '11px',
                color: 'var(--text-secondary, #888)',
              }}
              onMouseEnter={e => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.background = 'var(--bg-hover, rgba(0,0,0,0.06))'; }}
              onMouseLeave={e => { e.currentTarget.style.opacity = '0'; e.currentTarget.style.background = 'transparent'; }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
                <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
              </svg>
              <span>转为编辑</span>
            </button>
          )}
          {/* 保存为笔记按钮（仅 assistant 且有内容时显示） */}
          {msg.role === 'assistant' && msg.content && (
            <button
              onClick={handleSaveAsNote}
              disabled={saving}
              title="保存为知识卡片"
              className={styles.saveNoteBtn}
              style={{
                position: 'absolute',
                bottom: '8px',
                right: '8px',
                padding: '4px 8px',
                border: 'none',
                borderRadius: '6px',
                background: 'transparent',
                cursor: saving ? 'not-allowed' : 'pointer',
                opacity: saving ? 0.5 : 0,
                transition: 'opacity 0.15s, background 0.15s',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '11px',
                color: 'var(--text-secondary, #888)',
              }}
              onMouseEnter={e => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.background = 'var(--bg-hover, rgba(0,0,0,0.06))'; }}
              onMouseLeave={e => { e.currentTarget.style.opacity = '0'; e.currentTarget.style.background = 'transparent'; }}
            >
              {saving ? (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M12 6v6l4 2" />
                </svg>
              ) : (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M19 21l-7-5-7 5V5a2 2 0 012-2h10a2 2 0 012 2z" />
                </svg>
              )}
              <span>{saving ? '保存中' : '存为笔记'}</span>
            </button>
          )}
        </div>
      </div>
      <SaveToast visible={toast.visible} success={toast.success} />
    </>
  );
}, (prev, next) => {
  return prev.msg.id === next.msg.id
    && prev.msg.content === next.msg.content
    && prev.msg.toolResult === next.msg.toolResult
    && prev.msg.agentSteps === next.msg.agentSteps
    && prev.msg.thinkingContent === next.msg.thinkingContent
    && prev.isLast === next.isLast
    && prev.isChatting === next.isChatting
    && prev.paperId === next.paperId;
});

export default MessageItem;

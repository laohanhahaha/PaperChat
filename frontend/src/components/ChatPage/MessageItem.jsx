import React, { memo } from 'react';

const MessageItem = memo(function MessageItem({ msg, isLast, isChatting, renderMarkdown, styles }) {
  return (
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
      <div className={styles.messageBubble}>
        {msg.content ? (
          msg.role === 'assistant' ? renderMarkdown(msg.content) : msg.content
        ) : (
          isChatting && isLast ? (
            <div className={styles.thinkingDots}>
              <span></span><span></span><span></span>
            </div>
          ) : ''
        )}
      </div>
    </div>
  );
}, (prev, next) => {
  return prev.msg.id === next.msg.id
    && prev.msg.content === next.msg.content
    && prev.isLast === next.isLast
    && prev.isChatting === next.isChatting;
});

export default MessageItem;

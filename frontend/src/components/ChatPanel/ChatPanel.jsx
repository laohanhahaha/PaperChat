import React, { useState, useRef, useEffect, useCallback, memo } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useTranslation } from 'react-i18next';
import { useSessionStore } from '../../stores/sessionStore';
import { useMessageStore } from '../../stores/messageStore';
import { useChatConfigStore } from '../../stores/chatConfigStore';
import usePaperStore from '../../stores/paperStore';
import useSettingsStore from '../../stores/settingsStore';
import PaperSelector from '../PaperSelector/PaperSelector';
import MarkdownContent from '../../utils/MarkdownRenderer';
import { useTypewriter } from '../../hooks/useTypewriter';
import { useChatMessages } from '../../hooks/useChatMessages';
import { INTENT_LABELS } from '../../utils/chatConstants';
import styles from './ChatPanel.module.css';

// MessageItem 组件 - 使用 memo 优化渲染性能
const MessageItem = memo(function MessageItem({
  msg,
  isLast,
  isChatting,
  renderContentWithCitations,
  styles,
  isCrossDocMode,
  sources,
  crossDocSources,
  getPaperTitle,
  handleSourceClick
}) {
  return (
    <div
      className={`${styles.message} ${msg.role === 'user' ? styles.userMessage : styles.assistantMessage}`}
    >
      <div className={styles.bubble}>
        {msg.content ? (
          msg.role === 'assistant'
            ? renderContentWithCitations(msg.content)
            : msg.content
        ) : (isChatting && isLast ? (
          <span className={styles.typing}>思考中...</span>
        ) : '')}
      </div>

      {msg.role === 'assistant' &&
       !isChatting &&
       isLast && (
        <>
          {sources.length > 0 && !isCrossDocMode && (
            <div className={styles.sources}>
              <div className={styles.sourcesTitle}>引用来源：</div>
              {sources.map((source, idx) => (
                source.type === 'web' ? (
                  <a
                    key={idx}
                    className={`${styles.sourceItem} ${styles.webSource}`}
                    href={source.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <span className={styles.webSourceIcon}>🌐</span>
                    <span className={styles.webSourceTitle}>
                      {source.title || '网络来源'}
                    </span>
                    <span className={styles.sourceText}>
                      {source.text?.substring(0, 50)}...
                    </span>
                  </a>
                ) : (
                  <div
                    key={idx}
                    className={styles.sourceItem}
                    onClick={() => handleSourceClick(source.pages)}
                  >
                    <span className={styles.sourcePages}>
                      第 {source.pages?.join(', ') || '?'} 页
                    </span>
                    <span className={styles.sourceText}>
                      {source.text?.substring(0, 50)}...
                    </span>
                  </div>
                )
              ))}
            </div>
          )}

          {crossDocSources.length > 0 && isCrossDocMode && (
            <div className={`${styles.sources} ${styles.crossDocSources}`}>
              <div className={styles.sourcesTitle}>跨文档引用来源：</div>
              {crossDocSources.map((source, idx) => (
                <div
                  key={idx}
                  className={styles.sourceItem}
                  onClick={() => handleSourceClick(source.pages, source.paper_id)}
                >
                  <span className={styles.sourcePaper}>
                    {getPaperTitle(source.paper_id).slice(0, 20)}
                    {getPaperTitle(source.paper_id).length > 20 ? '...' : ''}
                  </span>
                  <span className={styles.sourcePages}>
                    第 {source.pages?.join(', ') || '?'} 页
                  </span>
                  <span className={styles.sourceText}>
                    {source.text?.substring(0, 40)}...
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}, (prev, next) => {
  // 只在这些属性变化时才重渲染
  return prev.msg.id === next.msg.id
    && prev.msg.content === next.msg.content
    && prev.isLast === next.isLast
    && prev.isChatting === next.isChatting
    && prev.isCrossDocMode === next.isCrossDocMode
    && prev.sources === next.sources
    && prev.crossDocSources === next.crossDocSources;
});

function ChatPanel({
  pdfText,
  paperId,
  isChatting,
  setIsChatting,
  sendRagMessage,
  sendCrossDocMessage,
  sendUnifiedChatMessage,
  onMessage,
  wsStatus,
  onNavigateToPage,
  onSwitchPaper
}) {
  const { t } = useTranslation();
  const [input, setInput] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showPaperSelector, setShowPaperSelector] = useState(false);
  const textareaRef = useRef(null);
  const currentSessionIdRef = useRef(null);
  const messagesRef = useRef(null);

  // Session Store
  const {
    sessions,
    currentSessionId,
    createSession,
    deleteSession,
    setCurrentSession,
    fetchMessages,
    getOrCreateSessionByPaper,
    createCrossDocSession,
  } = useSessionStore();
  
  // Message Store
  const {
    messages,
    sources,
    crossDocSources,
    addMessage,
    updateLastMessage,
    setSources,
    setCrossDocSources,
    hasMore,
    loadingMore,
    loadMoreMessages,
  } = useMessageStore();
  
  // Chat Config Store
  const {
    selectedPaperIds,
    isCrossDocMode,
    enableSearch,
    searchStatus,
    removePaperFromCrossDoc,
    clearCrossDocPapers,
    setCrossDocPapers,
    toggleSearch,
    setSearchStatus,
    clearSearchState,
  } = useChatConfigStore();

  const { papers } = usePaperStore();

  useEffect(() => {
    if (paperId) {
      getOrCreateSessionByPaper(paperId);
    }
  }, [paperId, getOrCreateSessionByPaper]);

  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  // ---- 虚拟滚动 ----
  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Virtual's useVirtualizer returns non-memoizable functions; this is expected and handled by skipping compilation
  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => messagesRef.current,
    estimateSize: () => 120,
    overscan: 5,
    measureElement: (el) => {
      return el.getBoundingClientRect().height;
    },
  });

  // 自动滚动到底部（仅在非加载更多时）
  const lastMessageContent = messages[messages.length - 1]?.content;
  useEffect(() => {
    if (messages.length > 0 && !loadingMore) {
      virtualizer.scrollToIndex(messages.length - 1, { align: 'end', behavior: 'smooth' });
    }
  }, [messages.length, lastMessageContent, virtualizer, loadingMore]);
  
  // ---- 滚动加载更多 ----
  const handleScroll = useCallback((e) => {
    const { scrollTop } = e.target;
    // 滚动到顶部且还有更多消息时加载更多
    if (scrollTop === 0 && hasMore && !loadingMore && currentSessionId) {
      loadMoreMessages(currentSessionId);
    }
  }, [hasMore, loadingMore, currentSessionId, loadMoreMessages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [input]);

  const handleComplete = useCallback(() => {
    setIsChatting(false);
  }, [setIsChatting]);

  const typewriter = useTypewriter(updateLastMessage, handleComplete, {
    charInterval: 50,
    charsPerTick: 3,
  });

  const { currentIntent, setCurrentIntent } = useChatMessages({
    onMessage,
    typewriter,
    currentSessionIdRef,
    setSources,
    setCrossDocSources,
    setSearchStatus,
    updateLastMessage,
    setCurrentSession,
    onError: useCallback((msg) => {
      console.error('问答错误:', msg.message);
      typewriter.stop();
      updateLastMessage(msg.message || '请求失败，请重试。');
      setIsChatting(false);
    }, [typewriter, updateLastMessage, setIsChatting]),
    onConfigUpdate: useCallback(() => {
      // 配置变更时刷新设置，使 SettingsPage 服务状态自动更新
      useSettingsStore.getState().fetchSettings();
    }, []),
  });

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || isChatting || wsStatus !== 'connected') return;

    const sessionId = currentSessionIdRef.current;

    addMessage({ role: 'user', content: trimmed });
    addMessage({ role: 'assistant', content: '' });

    setInput('');
    setIsChatting(true);
    setSources([]);
    setCrossDocSources([]);
    clearSearchState();
    setCurrentIntent(null);
    typewriter.reset();
    typewriter.start();

    if (sendUnifiedChatMessage) {
      sendUnifiedChatMessage(trimmed, paperId, selectedPaperIds, sessionId, enableSearch);
    } else if (isCrossDocMode && selectedPaperIds.length > 0) {
      sendCrossDocMessage(trimmed, selectedPaperIds, sessionId);
    } else {
      sendRagMessage(trimmed, paperId, sessionId, null, enableSearch);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewSession = async () => {
    if (isCrossDocMode && selectedPaperIds.length > 0) {
      await createCrossDocSession(selectedPaperIds, '跨文档对话');
    } else {
      await createSession(paperId, '新对话');
    }
    typewriter.reset();
  };

  const handleAddPaper = () => {
    setShowPaperSelector(true);
  };

  const handlePaperSelectorConfirm = async (selectedIds) => {
    if (selectedIds.length === 0) return;

    setCrossDocPapers(selectedIds);

    if (selectedIds.length >= 1) {
      await createCrossDocSession(selectedIds, '跨文档对话');
    }
  };

  const handleRemovePaper = (paperIdToRemove) => {
    removePaperFromCrossDoc(paperIdToRemove);
  };

  const handleClearCrossDoc = () => {
    clearCrossDocPapers();
  };

  const handleSwitchSession = async (sessionId) => {
    if (sessionId === currentSessionId) return;
    setCurrentSession(sessionId);
    await fetchMessages(sessionId, true); // true = reset and fetch from beginning
    typewriter.reset();
  };

  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    if (window.confirm('确定要删除这个会话吗？')) {
      await deleteSession(sessionId);
    }
  };

  const handleSourceClick = (pages, targetPaperId = null) => {
    if (targetPaperId && targetPaperId !== paperId && onSwitchPaper) {
      onSwitchPaper(targetPaperId, pages[0]);
    } else if (pages && pages.length > 0 && onNavigateToPage) {
      onNavigateToPage(pages[0]);
    }
  };

  const getPaperTitle = (pid) => {
    const paper = papers.find(p => p.id === pid);
    return paper ? paper.title : `论文 ${pid}`;
  };

  const renderContentWithCitations = (text) => {
    if (!text) return null;

    const parts = [];
    let key = 0;
    let lastIndex = 0;

    const crossDocRegex = /\[论文(\d+)\s*,?\s*p\.(\d+)\]/g;
    const singleDocRegex = /\[p\.(\d+)\]/g;

    let match;
    while ((match = crossDocRegex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(
          <span key={key++}>{renderMarkdown(text.slice(lastIndex, match.index))}</span>
        );
      }

      const paperId = parseInt(match[1], 10);
      const pageNum = parseInt(match[2], 10);
      const paperTitle = getPaperTitle(paperId);

      parts.push(
        <button
          key={key++}
          className={styles.citationLink}
          onClick={() => handleSourceClick([pageNum], paperId)}
          title={`${paperTitle} - 第 ${pageNum} 页`}
        >
          [论文{paperId}, p.{pageNum}]
        </button>
      );

      lastIndex = match.index + match[0].length;
    }

    const remainingText = text.slice(lastIndex);
    let singleLastIndex = 0;

    while ((match = singleDocRegex.exec(remainingText)) !== null) {
      if (match.index > singleLastIndex) {
        parts.push(
          <span key={key++}>{renderMarkdown(remainingText.slice(singleLastIndex, match.index))}</span>
        );
      }

      const pageNum = parseInt(match[1], 10);
      parts.push(
        <button
          key={key++}
          className={styles.citationLink}
          onClick={() => handleSourceClick([pageNum])}
          title={`跳转到第 ${pageNum} 页`}
        >
          [p.{pageNum}]
        </button>
      );

      singleLastIndex = match.index + match[0].length;
    }

    if (singleLastIndex < remainingText.length) {
      parts.push(
        <span key={key++}>{renderMarkdown(remainingText.slice(singleLastIndex))}</span>
      );
    }

    return parts.length > 0 ? parts : renderMarkdown(text);
  };

  const renderMarkdown = (text) => {
    if (!text) return null;
    return <MarkdownContent content={text} />;
  };

  const formatTime = (timeStr) => {
    if (!timeStr) return '';
    const date = new Date(timeStr);
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  if (!pdfText && !paperId) {
    return (
      <div className={styles.container}>
        <div className={styles.unifiedWelcome}>
          <h2>🔍 统一智能助手</h2>
          <p>在这里你可以：</p>
          <ul>
            <li><strong>章节概述</strong> - 输入"章节概述"或"概述"分析论文结构</li>
            <li><strong>深度分析</strong> - 输入"深度分析"或"详细分析"进行深入研究</li>
            <li><strong>核心知识点</strong> - 输入"核心知识点"提取关键概念</li>
            <li><strong>智能问答</strong> - 直接输入问题进行 RAG 检索问答</li>
            <li><strong>跨文档问答</strong> - 添加多篇论文进行跨文档分析</li>
            <li><strong>翻译/解释</strong> - 输入"翻译xxx"或"解释xxx"进行术语处理</li>
          </ul>
          <p className={styles.hint}>上传 PDF 论文后即可开始使用</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={`${styles.sidebar} ${sidebarOpen ? styles.sidebarOpen : styles.sidebarClosed}`}>
        <div className={styles.sidebarHeader}>
          <button className={styles.newSessionBtn} onClick={handleNewSession}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            {t('chat.newSession')}
          </button>
        </div>

        <div className={styles.crossDocSection}>
          <div className={styles.crossDocHeader}>
            <span className={styles.crossDocTitle}>跨文档问答</span>
            <button
              className={styles.addPaperBtn}
              onClick={handleAddPaper}
              title="添加论文"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <line x1="5" y1="12" x2="19" y2="12"></line>
              </svg>
              添加论文
            </button>
          </div>

          {selectedPaperIds.length > 0 && (
            <div className={styles.selectedPapers}>
              {selectedPaperIds.map(pid => (
                <div key={pid} className={styles.paperTag}>
                  <span className={styles.paperTagText} title={getPaperTitle(pid)}>
                    {getPaperTitle(pid).slice(0, 15)}{getPaperTitle(pid).length > 15 ? '...' : ''}
                  </span>
                  <button
                    className={styles.paperTagRemove}
                    onClick={() => handleRemovePaper(pid)}
                    title="移除"
                  >
                    ×
                  </button>
                </div>
              ))}
              {selectedPaperIds.length > 1 && (
                <button
                  className={styles.clearAllBtn}
                  onClick={handleClearCrossDoc}
                  title="清空选择"
                >
                  清空
                </button>
              )}
            </div>
          )}

          {selectedPaperIds.length === 0 && (
            <div className={styles.crossDocHint}>
              点击"添加论文"选择多篇论文进行跨文档问答
            </div>
          )}
        </div>

        <div className={styles.sessionList}>
          {sessions.map(session => (
            <div
              key={session.id}
              className={`${styles.sessionItem} ${session.id === currentSessionId ? styles.sessionItemActive : ''} ${session.is_cross_doc ? styles.crossDocSession : ''}`}
              onClick={() => handleSwitchSession(session.id)}
            >
              <div className={styles.sessionTitle}>
                {session.is_cross_doc && <span className={styles.crossDocBadge}>跨</span>}
                {session.title}
              </div>
              <div className={styles.sessionMeta}>
                {formatTime(session.updated_at)}
                {session.is_cross_doc && session.paper_ids && (
                  <span className={styles.paperCount}>· {session.paper_ids.length}篇</span>
                )}
              </div>
              <button
                className={styles.deleteSessionBtn}
                onClick={(e) => handleDeleteSession(e, session.id)}
                title="删除会话"
              >
                ×
              </button>
            </div>
          ))}
          {sessions.length === 0 && (
            <div className={styles.emptySessions}>暂无会话</div>
          )}
        </div>
      </div>

      <button
        className={styles.sidebarToggle}
        onClick={() => setSidebarOpen(!sidebarOpen)}
        title={sidebarOpen ? '收起侧边栏' : '展开侧边栏'}
      >
        {sidebarOpen ? '◀' : '▶'}
      </button>

      <div className={styles.chatArea}>
        <div ref={messagesRef} className={styles.messages} onScroll={handleScroll}>
          {/* 加载更多指示器 */}
          {loadingMore && (
            <div className={styles.loadingMoreIndicator}>
              <span className={styles.loadingSpinner}></span>
              加载更多消息...
            </div>
          )}
          {messages.length === 0 && (
            <div className={styles.welcome}>
              <p>💬 统一智能助手 - 有什么问题可以问我</p>
              {currentIntent && currentIntent.matched && (
                <div className={styles.intentIndicator}>
                  <span className={styles.intentBadge}>
                    {INTENT_LABELS[currentIntent.intent] || currentIntent.intent}
                  </span>
                  <span className={styles.intentHint}>
                    (置信度: {currentIntent.confidence})
                  </span>
                </div>
              )}
              <div className={styles.welcomeHints}>
                <p>📋 输入"章节概述" - 分析论文结构</p>
                <p>🔬 输入"深度分析" - 深入研究论文</p>
                <p>🎯 输入"核心知识点" - 提取关键概念</p>
                <p>📚 添加多篇论文后可以跨文档分析</p>
              </div>
              <p className={styles.welcomeHint}>回答中的 [p.X] 标记可以点击跳转到对应页面</p>
            </div>
          )}
          {messages.length > 0 && (
            <div style={{ height: virtualizer.getTotalSize(), width: '100%', position: 'relative' }}>
              {virtualizer.getVirtualItems().map((virtualRow) => {
                const msg = messages[virtualRow.index];
                const isLast = virtualRow.index === messages.length - 1;
                return (
                  <div
                    key={msg.id || `msg-${virtualRow.index}`}
                    data-index={virtualRow.index}
                    ref={virtualizer.measureElement}
                    style={{
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                  >
                    <MessageItem
                      msg={msg}
                      index={virtualRow.index}
                      isLast={isLast}
                      isChatting={isChatting}
                      renderContentWithCitations={renderContentWithCitations}
                      styles={styles}
                      isCrossDocMode={isCrossDocMode}
                      sources={sources}
                      crossDocSources={crossDocSources}
                      getPaperTitle={getPaperTitle}
                      handleSourceClick={handleSourceClick}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className={styles.searchControl}>
          <label className={styles.searchToggle}>
            <input
              type="checkbox"
              checked={enableSearch}
              onChange={toggleSearch}
              disabled={isChatting}
            />
            <span className={styles.toggleSlider}></span>
            <span>联网搜索</span>
          </label>
          {searchStatus === 'searching' && (
            <span className={styles.searchingIndicator}>
              <span className={styles.searchSpinner}></span>
              正在搜索网络...
            </span>
          )}
          {searchStatus === 'completed' && (
            <span className={styles.searchDone}>✓ 已获取网络信息</span>
          )}
        </div>
        <div className={styles.inputArea}>
          <textarea
            ref={textareaRef}
            className={styles.textarea}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t('chat.inputPlaceholder')}
            rows={1}
            disabled={isChatting}
          />
          <button
            className={styles.sendBtn}
            onClick={handleSend}
            disabled={!input.trim() || isChatting}
          >
            {t('chat.send')}
          </button>
        </div>
      </div>

      <PaperSelector
        isOpen={showPaperSelector}
        onClose={() => setShowPaperSelector(false)}
        onConfirm={handlePaperSelectorConfirm}
        initialSelectedIds={selectedPaperIds}
        maxSelection={10}
      />
    </div>
  );
}

export default ChatPanel;

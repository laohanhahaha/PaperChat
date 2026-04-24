import React, { useState, useEffect, useCallback, useRef } from 'react';
import WebViewPanel from '../components/WebView/WebViewPanel';
import { useVirtualizer } from '@tanstack/react-virtual';
import usePaperStore from '../stores/paperStore';
import useSettingsStore from '../stores/settingsStore';
import { useSessionStore } from '../stores/sessionStore';
import { useMessageStore } from '../stores/messageStore';
import { useChatConfigStore } from '../stores/chatConfigStore';
import PaperSelector from '../components/PaperSelector/PaperSelector';
import MarkdownContent from '../utils/MarkdownRenderer';
import { INTENT_LABELS, SUGGESTIONS } from '../utils/chatConstants';
import useWebSocket from '../hooks/useWebSocket';
import { useTypewriter } from '../hooks/useTypewriter';
import { useChatMessages } from '../hooks/useChatMessages';
import { useSessionManager } from '../hooks/useSessionManager';
import MessageItem from '../components/ChatPage/MessageItem';
import AgentProgress from '../components/ChatPage/AgentProgress';
import SelectedPapersBar from '../components/ChatPage/SelectedPapersBar';
import InputBar from '../components/ChatPage/InputBar';
import SessionSidebar from '../components/ChatPage/SessionSidebar';
import ModelSelector from '../components/Cost/ModelSelector';
import CostIndicator from '../components/Cost/CostIndicator';
import styles from './ChatPage.module.css';

let msgIdCounter = 0;
function genMsgId() {
  return `local-${Date.now()}-${++msgIdCounter}`;
}

function ChatPage() {
  const { papers, fetchPapers } = usePaperStore();

  // Session Store
  const {
    sessions,
    currentSessionId,
    fetchSessions,
    createSession,
    deleteSession,
    setCurrentSession,
    renameSession,
    autoNameSession,
    createCrossDocSession,
  } = useSessionStore();

  // Message Store
  const {
    messages,
    sources,
    crossDocSources,
    fetchMessages,
    addMessage,
    updateLastMessage,
    setLastMessageToolResult,
    addAgentStep,
    appendThinkingContent,
    markAgentComplete,
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
    setCrossDocPapers,
    removePaperFromCrossDoc,
    toggleSearch,
    setSearchStatus,
    clearSearchState,
  } = useChatConfigStore();

  const [input, setInput] = useState('');
  const [selectedPaperId, setSelectedPaperId] = useState(null);
  const [showPaperSelector, setShowPaperSelector] = useState(false);
  const [isChatting, setIsChatting] = useState(false);
  const [images, setImages] = useState([]);

  // WebView 状态
  const [webViewUrl, setWebViewUrl] = useState(null);
  const [showWebView, setShowWebView] = useState(false);
  const [webViewPlacement, setWebViewPlacement] = useState('bottom');
  const { status: wsStatus, sendUnifiedChatMessage, sendCancel, onMessage } = useWebSocket();

  const textareaRef = useRef(null);
  const currentSessionIdRef = useRef(null);
  const isChattingRef = useRef(false);
  const messageListRef = useRef(null);

  // 初始化加载
  useEffect(() => {
    fetchPapers({ page: 1, page_size: 100 });
    fetchSessions();
  }, [fetchPapers, fetchSessions]);

  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px';
    }
  }, [input]);

  // ---- Typewriter ----
  const handleComplete = useCallback(() => {
    setIsChatting(false);
    isChattingRef.current = false;
  }, []);

  const typewriter = useTypewriter(updateLastMessage, handleComplete, {
    charInterval: 50,
    charsPerTick: 3,
  });

  const resetStreamState = useCallback(() => {
    typewriter.stop();
    typewriter.reset();
    setIsChatting(false);
    isChattingRef.current = false;
  }, [typewriter]);

  // ---- 停止生成 ----
  const handleStop = useCallback(() => {
    sendCancel();
    if (typewriter.fullContentRef.current) {
      updateLastMessage(typewriter.fullContentRef.current + '\n\n*[已停止]*');
    } else {
      updateLastMessage('*[已停止]*');
    }
    resetStreamState();
  }, [sendCancel, updateLastMessage, resetStreamState, typewriter]);

  // ---- Hooks ----
  const { currentIntent, setCurrentIntent } = useChatMessages({
    onMessage,
    typewriter,
    isChattingRef,
    currentSessionIdRef,
    setSources,
    setCrossDocSources,
    setSearchStatus,
    updateLastMessage,
    setLastMessageToolResult,
    addAgentStep,
    appendThinkingContent,
    markAgentComplete,
    setCurrentSession,
    fetchSessions,
    onCancelled: useCallback(() => {
      if (typewriter.fullContentRef.current) {
        updateLastMessage(typewriter.fullContentRef.current + '\n\n*[已停止]*');
      } else {
        updateLastMessage('*[已停止]*');
      }
      resetStreamState();
    }, [typewriter, updateLastMessage, resetStreamState]),
    resetStreamState,
    onConfigUpdate: useCallback(() => {
      useSettingsStore.getState().fetchSettings();
    }, []),
  });

  const {
    handleNewSession,
    handleSwitchSession,
    handleDeleteSession,
    handleStartEditing,
    handleSaveTitle,
    handleEditKeyDown,
    editingSessionId,
    editingTitle,
    setEditingTitle,
  } = useSessionManager({
    isChatting,
    isCrossDocMode,
    selectedPaperIds,
    selectedPaperId,
    currentSessionId,
    handleStop,
    resetStreamState,
    createCrossDocSession,
    createSession,
    setCurrentSession,
    fetchMessages,
    deleteSession,
    renameSession,
  });

  // ---- 虚拟滚动 ----
  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Virtual's useVirtualizer returns non-memoizable functions; this is expected and handled by skipping compilation
  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => messageListRef.current,
    estimateSize: () => 120,
    overscan: 5,
    measureElement: (el) => {
      // 使用 getBoundingClientRect 获取精确高度
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

  // ---- 发送消息 ----
  const handleSend = (text) => {
    const trimmed = (text || input).trim();
    if (!trimmed || isChatting || wsStatus !== 'connected') return;

    const sessionId = currentSessionIdRef.current;
    const currentSession = sessions.find(s => s.id === sessionId);
    const isFirstMessage = messages.length === 0;
    const needsAutoName = currentSession && isFirstMessage &&
      (currentSession.title === '新对话' || currentSession.title === '跨文档对话');

    if (needsAutoName) {
      autoNameSession(sessionId, trimmed);
    }

    addMessage({ id: genMsgId(), role: 'user', content: trimmed });
    addMessage({ id: genMsgId(), role: 'assistant', content: '' });

    setInput('');
    setIsChatting(true);
    isChattingRef.current = true;
    setSources([]);
    setCrossDocSources([]);
    clearSearchState();
    setCurrentIntent(null);
    typewriter.reset();
    typewriter.start();

    const readyImages = images
      .filter((i) => i.status === 'ready')
      .map((i) => ({
        image_id: i.image_id,
        type: i.file?.type,
        name: i.file?.name,
      }));

    sendUnifiedChatMessage(trimmed, selectedPaperId, selectedPaperIds, sessionId, enableSearch, readyImages);
    setImages([]);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleAddImage = async (file) => {
    if (file.size > 10 * 1024 * 1024) {
      alert('图片不能超过10MB');
      return;
    }
    if (images.length >= 4) {
      alert('最多上传4张图片');
      return;
    }

    const idx = images.length;
    setImages((prev) => [...prev, { file, status: 'uploading', progress: 0 }]);

    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch('/api/v1/upload/image', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) {
        throw new Error(`上传失败: ${res.status}`);
      }
      const data = await res.json();

      setImages((prev) =>
        prev.map((img, i) =>
          i === idx
            ? {
                ...img,
                status: 'ready',
                image_id: data.image_id,
                thumbnailUrl: data.thumbnail_url,
              }
            : img
        )
      );
    } catch (err) {
      setImages((prev) =>
        prev.map((img, i) =>
          i === idx ? { ...img, status: 'error', error: err.message } : img
        )
      );
    }
  };

  const handleRemoveImage = (idx) => {
    setImages((prev) => prev.filter((_, i) => i !== idx));
  };

  const handlePaperSelect = (selectedIds) => {
    setCrossDocPapers(selectedIds);
    if (selectedIds.length === 1) {
      setSelectedPaperId(selectedIds[0]);
    } else if (selectedIds.length > 1) {
      setSelectedPaperId(null);
    }
    setShowPaperSelector(false);
  };

  // ---- WebView 处理 ----
  const handleOpenWebView = useCallback((url, placement = 'bottom') => {
    setWebViewUrl(url);
    setWebViewPlacement(placement);
    setShowWebView(true);
  }, []);

  const handleCloseWebView = useCallback(() => {
    setShowWebView(false);
  }, []);

  // 拦截消息列表区域内的外部链接
  const handleMessageListClick = useCallback((e) => {
    const anchor = e.target.closest('a[href]');
    if (!anchor) return;
    const href = anchor.getAttribute('href');
    if (!href) return;
    if (/^https?:\/\//i.test(href)) {
      e.preventDefault();
      e.stopPropagation();
      handleOpenWebView(href, 'bottom');
    }
  }, [handleOpenWebView]);

  // ---- 辅助函数 ----
  const getPaperTitle = (pid) => {
    const paper = papers.find(p => p.id === pid);
    return paper ? paper.title : `论文 ${pid}`;
  };

  const formatTime = (timeStr) => {
    if (!timeStr) return '';
    const date = new Date(timeStr);
    const now = new Date();
    const diff = now - date;
    if (diff < 86400000) {
      return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    }
    if (diff < 604800000) {
      const days = Math.floor(diff / 86400000);
      return `${days}天前`;
    }
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
  };

  const renderMarkdown = (text) => {
    if (!text) return null;
    return <MarkdownContent content={text} />;
  };

  const hasConversation = messages.length > 0;
  const hasPapers = selectedPaperIds.length > 0 || selectedPaperId;

  return (
    <div className={styles.layout}>
      <SessionSidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        editingSessionId={editingSessionId}
        editingTitle={editingTitle}
        setEditingTitle={setEditingTitle}
        handleNewSession={handleNewSession}
        handleSwitchSession={handleSwitchSession}
        handleDeleteSession={handleDeleteSession}
        handleStartEditing={handleStartEditing}
        handleSaveTitle={handleSaveTitle}
        handleEditKeyDown={handleEditKeyDown}
        formatTime={formatTime}
        styles={styles}
      />

      <main className={styles.main}>
        {!hasConversation ? (
          <div className={styles.welcomeArea}>
            <SelectedPapersBar
              selectedPaperIds={selectedPaperIds}
              getPaperTitle={getPaperTitle}
              removePaperFromCrossDoc={removePaperFromCrossDoc}
              onOpenSelector={() => setShowPaperSelector(true)}
              styles={styles}
            />
            <div className={styles.welcomeCenter}>
              <h1 className={styles.welcomeTitle}>有什么我能帮你的吗？</h1>
              {!hasPapers && (
                <p className={styles.welcomeSubtitle}>请先选择论文，然后开始智能问答</p>
              )}
              <div className={styles.suggestions}>
                {SUGGESTIONS.map((s, i) => (
                  <button
                    key={i}
                    className={styles.suggestionChip}
                    onClick={() => hasPapers && handleSend(s.text)}
                    disabled={!hasPapers || isChatting || wsStatus !== 'connected'}
                  >
                    {s.text}
                  </button>
                ))}
              </div>
            </div>
            <InputBar
              input={input}
              setInput={setInput}
              textareaRef={textareaRef}
              handleKeyDown={handleKeyDown}
              handleSend={handleSend}
              handleStop={handleStop}
              isChatting={isChatting}
              hasPapers={hasPapers}
              isWelcome={true}
              enableSearch={enableSearch}
              toggleSearch={toggleSearch}
              searchStatus={searchStatus}
              wsStatus={wsStatus}
              onOpenSelector={() => setShowPaperSelector(true)}
              styles={styles}
              costSlot={<><ModelSelector /><CostIndicator sessionId={currentSessionId} /></>}
              images={images}
              onAddImage={handleAddImage}
              onRemoveImage={handleRemoveImage}
            />
          </div>
        ) : (
          <div className={styles.chatArea}>
            <SelectedPapersBar
              selectedPaperIds={selectedPaperIds}
              getPaperTitle={getPaperTitle}
              removePaperFromCrossDoc={removePaperFromCrossDoc}
              onOpenSelector={() => setShowPaperSelector(true)}
              styles={styles}
            />
            {currentIntent && currentIntent.matched && (
              <div className={styles.intentBar}>
                <span className={styles.intentBadge}>
                  {INTENT_LABELS[currentIntent.intent] || currentIntent.intent}
                </span>
              </div>
            )}

            <div ref={messageListRef} className={styles.messageList} onScroll={handleScroll} onClick={handleMessageListClick}>
              {/* 加载更多指示器 */}
              {loadingMore && (
                <div className={styles.loadingMoreIndicator}>
                  <span className={styles.loadingSpinner}></span>
                  加载更多消息...
                </div>
              )}
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
                        renderMarkdown={renderMarkdown}
                        styles={styles}
                        paperId={selectedPaperId || (selectedPaperIds.length === 1 ? selectedPaperIds[0] : null)}
                      />
                    </div>
                  );
                })}
              </div>

              {!isChatting && messages.length > 0 && messages[messages.length - 1]?.role === 'assistant' && (
                <>
                  {/* Agent 推理过程展示 */}
                  {messages[messages.length - 1]?.agentSteps?.length > 0 && (
                    <AgentProgress
                      steps={messages[messages.length - 1].agentSteps}
                      isRunning={false}
                    />
                  )}
                  {sources.length > 0 && !isCrossDocMode && (
                    <div className={styles.sourcesBlock}>
                      <div className={styles.sourcesLabel}>📎 引用来源</div>
                      {sources.map((source, idx) => (
                        source.type === 'web' ? (
                          <a key={`src-${idx}`} className={styles.sourceChip} href={source.href} target="_blank" rel="noopener noreferrer">
                            🌐 {source.title || '网络来源'}
                          </a>
                        ) : (
                          <span key={`src-${idx}`} className={styles.sourceChip}>
                            📄 第 {source.pages?.join(', ') || '?'} 页
                          </span>
                        )
                      ))}
                    </div>
                  )}
                  {crossDocSources.length > 0 && isCrossDocMode && (
                    <div className={styles.sourcesBlock}>
                      <div className={styles.sourcesLabel}>📎 跨文档引用</div>
                      {crossDocSources.map((source, idx) => (
                        <span key={`csrc-${idx}`} className={styles.sourceChip}>
                          📄 {getPaperTitle(source.paper_id).slice(0, 15)} · p.{source.pages?.join(',')}
                        </span>
                      ))}
                    </div>
                  )}
                </>
              )}

              {/* Agent 推理过程展示（运行中）*/}
              {isChatting && messages[messages.length - 1]?.agentSteps?.length > 0 && (
                <AgentProgress
                  steps={messages[messages.length - 1].agentSteps}
                  isRunning={true}
                />
              )}
            </div>

            <InputBar
              input={input}
              setInput={setInput}
              textareaRef={textareaRef}
              handleKeyDown={handleKeyDown}
              handleSend={handleSend}
              handleStop={handleStop}
              isChatting={isChatting}
              hasPapers={hasPapers}
              isWelcome={false}
              enableSearch={enableSearch}
              toggleSearch={toggleSearch}
              searchStatus={searchStatus}
              wsStatus={wsStatus}
              onOpenSelector={() => setShowPaperSelector(true)}
              styles={styles}
              costSlot={<><ModelSelector /><CostIndicator sessionId={currentSessionId} /></>}
              images={images}
              onAddImage={handleAddImage}
              onRemoveImage={handleRemoveImage}
            />
          </div>
        )}
      </main>

      <PaperSelector
        isOpen={showPaperSelector}
        onClose={() => setShowPaperSelector(false)}
        onConfirm={handlePaperSelect}
        initialSelectedIds={selectedPaperIds}
        maxSelection={10}
      />

      {/* WebView 面板 */}
      {showWebView && webViewUrl && (
        <WebViewPanel
          url={webViewUrl}
          placement={webViewPlacement}
          onClose={handleCloseWebView}
        />
      )}
    </div>
  );
}

export default ChatPage;

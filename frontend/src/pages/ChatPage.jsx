import { useState, useEffect, useCallback, useRef } from 'react';
import usePaperStore from '../stores/paperStore';
import useChatStore from '../stores/chatStore';
import PaperSelector from '../components/PaperSelector/PaperSelector';
import MarkdownContent from '../utils/MarkdownRenderer';
import useWebSocket from '../hooks/useWebSocket';
import styles from './ChatPage.module.css';

const CHAR_INTERVAL = 30;

let msgIdCounter = 0;
function genMsgId() {
  return `local-${Date.now()}-${++msgIdCounter}`;
}

const INTENT_LABELS = {
  'chapter_overview': '📋 章节概述',
  'deep_analysis': '🔬 深度分析',
  'key_points': '🎯 核心知识点',
  'comparison': '📊 对比分析',
  'summary': '📝 摘要总结',
  'translate': '🌐 翻译',
  'explain': '📖 术语解释',
  'cross_doc': '📚 跨文档问答',
  'quality_assessment': '⚖️ 质量评估',
  'outline': '📃 生成提纲',
  'simple_qa': '💬 智能问答'
};

const SUGGESTIONS = [
  { text: '帮我概述这篇论文的章节结构' },
  { text: '对这篇论文进行深度分析' },
  { text: '提取论文的核心知识点' },
  { text: '生成论文摘要总结' },
  { text: '翻译论文的关键段落' },
  { text: '评估论文的研究质量' },
];

function ChatPage() {
  const { papers, fetchPapers } = usePaperStore();
  const {
    sessions,
    currentSessionId,
    messages,
    sources,
    selectedPaperIds,
    crossDocSources,
    isCrossDocMode,
    enableSearch,
    searchStatus,
    fetchSessions,
    createSession,
    deleteSession,
    setCurrentSession,
    fetchMessages,
    addMessage,
    updateLastMessage,
    setSources,
    setCrossDocSources,
    setCrossDocPapers,
    removePaperFromCrossDoc,
    createCrossDocSession,
    toggleSearch,
    setSearchStatus,
    clearSearchState,
    renameSession,
    autoNameSession,
  } = useChatStore();

  const [input, setInput] = useState('');
  const [selectedPaperId, setSelectedPaperId] = useState(null);
  const [showPaperSelector, setShowPaperSelector] = useState(false);
  const [isChatting, setIsChatting] = useState(false);
  const [currentIntent, setCurrentIntent] = useState(null);
  const [editingSessionId, setEditingSessionId] = useState(null);
  const [editingTitle, setEditingTitle] = useState('');
  const { status: wsStatus, sendUnifiedChatMessage, sendCancel, onMessage } = useWebSocket();

  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fullContentRef = useRef('');
  const displayedLenRef = useRef(0);
  const timerRef = useRef(null);
  const isDoneRef = useRef(false);
  const currentSessionIdRef = useRef(null);
  const isChattingRef = useRef(false);

  useEffect(() => {
    fetchPapers({ page: 1, page_size: 100 });
    fetchSessions();
  }, [fetchPapers, fetchSessions]);

  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + 'px';
    }
  }, [input]);

  const resetStreamState = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    fullContentRef.current = '';
    displayedLenRef.current = 0;
    isDoneRef.current = false;
    setIsChatting(false);
    isChattingRef.current = false;
  }, []);

  const tickFnRef = useRef(null);

  useEffect(() => {
    tickFnRef.current = () => {
      if (!isChattingRef.current) return;
      const full = fullContentRef.current;
      const currentLen = displayedLenRef.current;
      if (currentLen < full.length) {
        const step = Math.min(3, full.length - currentLen);
        displayedLenRef.current = currentLen + step;
        updateLastMessage(full.slice(0, displayedLenRef.current));
        timerRef.current = setTimeout(() => tickFnRef.current?.(), CHAR_INTERVAL);
      } else if (isDoneRef.current) {
        updateLastMessage(full);
        setIsChatting(false);
        isChattingRef.current = false;
        timerRef.current = null;
      } else {
        timerRef.current = null;
      }
    };
  }, [updateLastMessage]);

  const startTick = useCallback(() => {
    if (!timerRef.current && isChattingRef.current) {
      timerRef.current = setTimeout(() => tickFnRef.current?.(), CHAR_INTERVAL);
    }
  }, []);

  useEffect(() => {
    const unsubs = [
      onMessage('rag_chat_chunk', (msg) => {
        if (!isChattingRef.current) return;
        fullContentRef.current += msg.content;
        startTick();
      }),
      onMessage('rag_sources', (msg) => { setSources(msg.sources || []); }),
      onMessage('cross_doc_chunk', (msg) => {
        if (!isChattingRef.current) return;
        fullContentRef.current += msg.content;
        startTick();
      }),
      onMessage('cross_doc_sources', (msg) => { setCrossDocSources(msg.sources || []); }),
      onMessage('search_status', (msg) => { setSearchStatus(msg.status); }),
      onMessage('analyze_chunk', (msg) => {
        if (!isChattingRef.current) return;
        fullContentRef.current += msg.data;
        startTick();
      }),
      onMessage('deep_analyze_chunk', (msg) => {
        if (!isChattingRef.current) return;
        fullContentRef.current += msg.data;
        startTick();
      }),
      onMessage('intent_detected', (msg) => {
        setCurrentIntent({ intent: msg.intent, tool: msg.tool, confidence: msg.confidence, matched: msg.matched });
      }),
      onMessage('done', (msg) => {
        if (['rag_chat', 'cross_doc_chat', 'analyze', 'deep_analyze'].includes(msg.channel)) {
          isDoneRef.current = true;
          if (isChattingRef.current) startTick();
          if (msg.session_id && msg.session_id !== currentSessionIdRef.current) {
            currentSessionIdRef.current = msg.session_id;
            setCurrentSession(msg.session_id);
            fetchSessions();
          }
        }
      }),
      onMessage('cancelled', () => {
        if (fullContentRef.current) {
          updateLastMessage(fullContentRef.current + '\n\n*[已停止]*');
        } else {
          updateLastMessage('*[已停止]*');
        }
        resetStreamState();
      }),
      onMessage('error', (msg) => {
        console.error('问答错误:', msg.message);
        updateLastMessage(msg.message || '请求失败，请重试。');
        resetStreamState();
      }),
    ];
    return () => {
      unsubs.forEach(fn => fn());
    };
  }, [onMessage, startTick, setSources, setCrossDocSources, setSearchStatus, updateLastMessage, setCurrentSession, fetchSessions, resetStreamState]);

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, []);

  const handleStop = useCallback(() => {
    sendCancel();
    if (fullContentRef.current) {
      updateLastMessage(fullContentRef.current + '\n\n*[已停止]*');
    } else {
      updateLastMessage('*[已停止]*');
    }
    resetStreamState();
  }, [sendCancel, updateLastMessage, resetStreamState]);

  const handlePaperSelect = (selectedIds) => {
    setCrossDocPapers(selectedIds);
    if (selectedIds.length === 1) {
      setSelectedPaperId(selectedIds[0]);
    } else if (selectedIds.length > 1) {
      setSelectedPaperId(null);
    }
    setShowPaperSelector(false);
  };

  const handleSend = (text) => {
    const trimmed = (text || input).trim();
    if (!trimmed || isChatting || wsStatus !== 'connected') return;

    const sessionId = currentSessionIdRef.current;
    
    // 检查是否需要自动命名（第一条消息且标题为"新对话"或"跨文档对话"）
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
    fullContentRef.current = '';
    displayedLenRef.current = 0;
    isDoneRef.current = false;
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }

    sendUnifiedChatMessage(trimmed, selectedPaperId, selectedPaperIds, sessionId, enableSearch);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleNewSession = async () => {
    if (isChatting) handleStop();
    if (isCrossDocMode && selectedPaperIds.length > 0) {
      await createCrossDocSession(selectedPaperIds, '跨文档对话');
    } else {
      await createSession(selectedPaperId, '新对话');
    }
    resetStreamState();
  };

  const handleSwitchSession = async (sessionId) => {
    if (sessionId === currentSessionId) return;
    if (isChatting) handleStop();
    resetStreamState();
    setCurrentSession(sessionId);
    await fetchMessages(sessionId);
  };

  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    if (window.confirm('确定要删除这个会话吗？')) {
      if (sessionId === currentSessionId && isChatting) handleStop();
      await deleteSession(sessionId);
    }
  };

  // 开始编辑会话标题
  const handleStartEditing = (e, session) => {
    e.stopPropagation();
    setEditingSessionId(session.id);
    setEditingTitle(session.title);
  };

  // 保存编辑的标题
  const handleSaveTitle = async () => {
    if (!editingSessionId) return;
    
    const trimmedTitle = editingTitle.trim();
    if (trimmedTitle) {
      await renameSession(editingSessionId, trimmedTitle);
    }
    setEditingSessionId(null);
    setEditingTitle('');
  };

  // 取消编辑
  const handleCancelEditing = () => {
    setEditingSessionId(null);
    setEditingTitle('');
  };

  // 处理编辑时的键盘事件
  const handleEditKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSaveTitle();
    } else if (e.key === 'Escape') {
      handleCancelEditing();
    }
  };

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

  const renderSelectedPapers = () => (
    <div className={styles.selectedPapersBar}>
      <div className={styles.selectedPapersContent}>
        {selectedPaperIds.length > 0 ? (
          <>
            {selectedPaperIds.map(pid => (
              <div key={pid} className={styles.selectedPaperTag}>
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
            ))}
            <button 
              className={styles.addPaperChip} 
              onClick={() => setShowPaperSelector(true)}
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
            onClick={() => setShowPaperSelector(true)}
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

  const renderInputBar = (isWelcome) => (
    <div className={styles.inputWrapper}>
      <div className={styles.inputBox}>
        <button
          className={styles.attachBtn}
          onClick={() => setShowPaperSelector(true)}
          title="选择论文"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
          </svg>
        </button>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={hasPapers ? '输入你的问题...' : '请先选择论文...'}
          rows={1}
          disabled={isChatting || (isWelcome && !hasPapers)}
        />
        {isChatting ? (
          <button className={`${styles.sendBtn} ${styles.stopBtn}`} onClick={handleStop} title="停止生成">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          </button>
        ) : (
          <button
            className={`${styles.sendBtn} ${input.trim() ? styles.sendBtnActive : ''}`}
            onClick={() => handleSend()}
            disabled={!input.trim() || (isWelcome && !hasPapers)}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
            </svg>
          </button>
        )}
      </div>
      <div className={styles.inputActions}>
        <label className={styles.searchToggle}>
          <input type="checkbox" checked={enableSearch} onChange={toggleSearch} disabled={isChatting} />
          <span className={styles.toggleDot}></span>
          <span>联网搜索</span>
        </label>
        {searchStatus === 'searching' && (
          <span className={styles.searchingHint}><span className={styles.dot}></span>搜索中...</span>
        )}
        {searchStatus === 'completed' && (
          <span className={styles.searchDoneHint}>✓ 已获取网络信息</span>
        )}
        {wsStatus !== 'connected' && (
          <span className={styles.wsHint}>⚠ 连接中...</span>
        )}
      </div>
    </div>
  );

  return (
    <div className={styles.layout}>
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

      <main className={styles.main}>
        {!hasConversation ? (
          <div className={styles.welcomeArea}>
            {renderSelectedPapers()}
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
            {renderInputBar(true)}
          </div>
        ) : (
          <div className={styles.chatArea}>
            {renderSelectedPapers()}
            {currentIntent && currentIntent.matched && (
              <div className={styles.intentBar}>
                <span className={styles.intentBadge}>
                  {INTENT_LABELS[currentIntent.intent] || currentIntent.intent}
                </span>
              </div>
            )}

            <div className={styles.messageList}>
              {messages.map((msg, index) => (
                <div
                  key={msg.id || `msg-${index}`}
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
                      isChatting && index === messages.length - 1 ? (
                        <div className={styles.thinkingDots}>
                          <span></span><span></span><span></span>
                        </div>
                      ) : ''
                    )}
                  </div>
                </div>
              ))}

              {!isChatting && messages.length > 0 && messages[messages.length - 1]?.role === 'assistant' && (
                <>
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
              <div ref={messagesEndRef} />
            </div>

            {renderInputBar(false)}
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
    </div>
  );
}

export default ChatPage;

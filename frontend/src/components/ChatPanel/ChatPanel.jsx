import { useState, useRef, useEffect, useCallback } from 'react';
import useChatStore from '../../stores/chatStore';
import usePaperStore from '../../stores/paperStore';
import PaperSelector from '../PaperSelector/PaperSelector';
import MarkdownContent from '../../utils/MarkdownRenderer';
import styles from './ChatPanel.module.css';

const CHAR_INTERVAL = 30;

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
  const [input, setInput] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showPaperSelector, setShowPaperSelector] = useState(false);
  const [currentIntent, setCurrentIntent] = useState(null);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fullContentRef = useRef('');
  const displayedLenRef = useRef(0);
  const timerRef = useRef(null);
  const isDoneRef = useRef(false);
  const currentSessionIdRef = useRef(null);

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
    getOrCreateSessionByPaper,
    addPaperToCrossDoc,
    removePaperFromCrossDoc,
    clearCrossDocPapers,
    setCrossDocPapers,
    createCrossDocSession,
    toggleSearch,
    setSearchStatus,
    clearSearchState
  } = useChatStore();

  const { papers, fetchPapers } = usePaperStore();

  useEffect(() => {
    if (paperId) {
      getOrCreateSessionByPaper(paperId);
    }
  }, [paperId, getOrCreateSessionByPaper]);

  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [input]);

  const tickDisplay = useCallback(() => {
    const full = fullContentRef.current;
    const currentLen = displayedLenRef.current;

    if (currentLen < full.length) {
      displayedLenRef.current = currentLen + 1;
      const displayed = full.slice(0, displayedLenRef.current);
      updateLastMessage(displayed);
      timerRef.current = setTimeout(tickDisplay, CHAR_INTERVAL);
    } else if (isDoneRef.current) {
      setIsChatting(false);
      timerRef.current = null;
    } else {
      timerRef.current = null;
    }
  }, [updateLastMessage, setIsChatting]);

  const startTick = useCallback(() => {
    if (!timerRef.current) {
      timerRef.current = setTimeout(tickDisplay, CHAR_INTERVAL);
    }
  }, [tickDisplay]);

  useEffect(() => {
    const unsubRagChunk = onMessage('rag_chat_chunk', (msg) => {
      fullContentRef.current += msg.content;
      startTick();
    });

    const unsubRagSources = onMessage('rag_sources', (msg) => {
      setSources(msg.sources || []);
    });

    const unsubCrossDocChunk = onMessage('cross_doc_chunk', (msg) => {
      fullContentRef.current += msg.content;
      startTick();
    });

    const unsubCrossDocSources = onMessage('cross_doc_sources', (msg) => {
      setCrossDocSources(msg.sources || []);
    });

    const unsubSearchStatus = onMessage('search_status', (msg) => {
      setSearchStatus(msg.status);
    });

    const unsubAnalyzeChunk = onMessage('analyze_chunk', (msg) => {
      fullContentRef.current += msg.data;
      startTick();
    });

    const unsubDeepAnalyzeChunk = onMessage('deep_analyze_chunk', (msg) => {
      fullContentRef.current += msg.data;
      startTick();
    });

    const unsubIntentDetected = onMessage('intent_detected', (msg) => {
      setCurrentIntent({
        intent: msg.intent,
        tool: msg.tool,
        confidence: msg.confidence,
        matched: msg.matched
      });
    });

    const unsubDone = onMessage('done', (msg) => {
      if (['rag_chat', 'cross_doc_chat', 'analyze', 'deep_analyze'].includes(msg.channel)) {
        isDoneRef.current = true;
        startTick();
        if (msg.session_id) {
          currentSessionIdRef.current = msg.session_id;
          setCurrentSession(msg.session_id);
        }
      }
    });

    const unsubError = onMessage('error', (msg) => {
      console.error('问答错误:', msg.message);
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      updateLastMessage('请求失败，请重试。');
      setIsChatting(false);
    });

    return () => {
      unsubRagChunk();
      unsubRagSources();
      unsubCrossDocChunk();
      unsubCrossDocSources();
      unsubSearchStatus();
      unsubAnalyzeChunk();
      unsubDeepAnalyzeChunk();
      unsubIntentDetected();
      unsubDone();
      unsubError();
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [onMessage, startTick, setSources, setCrossDocSources, setSearchStatus, setIsChatting, updateLastMessage, setCurrentSession]);

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
    fullContentRef.current = '';
    displayedLenRef.current = 0;
    isDoneRef.current = false;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

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
    fullContentRef.current = '';
    displayedLenRef.current = 0;
    isDoneRef.current = false;
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
    await fetchMessages(sessionId);
    fullContentRef.current = '';
    displayedLenRef.current = 0;
    isDoneRef.current = false;
  };

  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    if (window.confirm('确定要删除这个会话吗？')) {
      await deleteSession(sessionId);
    }
  };

  const handleSourceClick = (pages, paperId = null) => {
    if (paperId && paperId !== paperId && onSwitchPaper) {
      onSwitchPaper(paperId, pages[0]);
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
            新建对话
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
        <div className={styles.messages}>
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
          {messages.map((msg, index) => (
            <div
              key={msg.id || index}
              className={`${styles.message} ${msg.role === 'user' ? styles.userMessage : styles.assistantMessage}`}
            >
              <div className={styles.bubble}>
                {msg.content ? (
                  msg.role === 'assistant'
                    ? renderContentWithCitations(msg.content)
                    : msg.content
                ) : (isChatting && index === messages.length - 1 ? (
                  <span className={styles.typing}>思考中...</span>
                ) : '')}
              </div>

              {msg.role === 'assistant' &&
               !isChatting &&
               index === messages.length - 1 && (
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
          ))}
          <div ref={messagesEndRef} />
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
            placeholder="输入你的问题，或输入功能关键词（如：章节概述、深度分析）..."
            rows={1}
            disabled={isChatting}
          />
          <button
            className={styles.sendBtn}
            onClick={handleSend}
            disabled={!input.trim() || isChatting}
          >
            发送
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

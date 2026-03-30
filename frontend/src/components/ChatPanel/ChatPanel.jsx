import { useState, useRef, useEffect, useCallback } from 'react';
import useChatStore from '../../stores/chatStore';
import usePaperStore from '../../stores/paperStore';
import PaperSelector from '../PaperSelector/PaperSelector';
import MarkdownContent from '../../utils/MarkdownRenderer';
import styles from './ChatPanel.module.css';

const CHAR_INTERVAL = 30; // 每个字符的显示间隔（毫秒）

function ChatPanel({ 
  pdfText, 
  paperId, 
  isChatting, 
  setIsChatting, 
  sendRagMessage, 
  sendCrossDocMessage,
  onMessage, 
  wsStatus,
  onNavigateToPage,
  onSwitchPaper
}) {
  const [input, setInput] = useState('');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [showPaperSelector, setShowPaperSelector] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fullContentRef = useRef('');       // 已从服务端收到的完整文本
  const displayedLenRef = useRef(0);       // 当前已显示的字符数
  const timerRef = useRef(null);           // 逐字显示定时器
  const isDoneRef = useRef(false);         // 服务端是否已发送完毕
  const currentSessionIdRef = useRef(null); // 当前会话ID

  // 使用 chatStore
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

  // 使用 paperStore 获取论文列表
  const { papers, fetchPapers } = usePaperStore();

  // 初始化：加载会话列表
  useEffect(() => {
    if (paperId) {
      getOrCreateSessionByPaper(paperId);
    }
  }, [paperId, getOrCreateSessionByPaper]);

  // 同步 currentSessionId 到 ref
  useEffect(() => {
    currentSessionIdRef.current = currentSessionId;
  }, [currentSessionId]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 自动调整输入框高度
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 120) + 'px';
    }
  }, [input]);

  // 逐字显示的核心函数
  const tickDisplay = useCallback(() => {
    const full = fullContentRef.current;
    const currentLen = displayedLenRef.current;

    if (currentLen < full.length) {
      displayedLenRef.current = currentLen + 1;
      const displayed = full.slice(0, displayedLenRef.current);
      updateLastMessage(displayed);
      timerRef.current = setTimeout(tickDisplay, CHAR_INTERVAL);
    } else if (isDoneRef.current) {
      // 服务端已完成且所有字符已显示
      setIsChatting(false);
      timerRef.current = null;
    } else {
      // 等待更多数据到来，暂停定时器
      timerRef.current = null;
    }
  }, [updateLastMessage, setIsChatting]);

  // 启动逐字显示（如果定时器未运行）
  const startTick = useCallback(() => {
    if (!timerRef.current) {
      timerRef.current = setTimeout(tickDisplay, CHAR_INTERVAL);
    }
  }, [tickDisplay]);

  // 监听 WebSocket 消息
  useEffect(() => {
    // RAG 问答片段
    const unsubRagChunk = onMessage('rag_chat_chunk', (msg) => {
      fullContentRef.current += msg.content;
      startTick();
    });

    // 引用来源
    const unsubRagSources = onMessage('rag_sources', (msg) => {
      setSources(msg.sources || []);
    });

    // 跨文档问答片段
    const unsubCrossDocChunk = onMessage('cross_doc_chunk', (msg) => {
      fullContentRef.current += msg.content;
      startTick();
    });

    // 跨文档引用来源
    const unsubCrossDocSources = onMessage('cross_doc_sources', (msg) => {
      setCrossDocSources(msg.sources || []);
    });

    // 搜索状态
    const unsubSearchStatus = onMessage('search_status', (msg) => {
      setSearchStatus(msg.status);
    });

    // 完成信号
    const unsubDone = onMessage('done', (msg) => {
      if (msg.channel === 'rag_chat' || msg.channel === 'cross_doc_chat') {
        isDoneRef.current = true;
        startTick();
        // 更新当前会话ID（如果是新会话）
        if (msg.session_id) {
          currentSessionIdRef.current = msg.session_id;
          setCurrentSession(msg.session_id);
        }
      }
    });

    // 错误处理
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

    // 如果没有当前会话，先创建一个
    const sessionId = currentSessionIdRef.current;
    
    // 添加用户消息
    addMessage({ role: 'user', content: trimmed });
    // 添加空的助手消息（用于流式显示）
    addMessage({ role: 'assistant', content: '' });
    
    setInput('');
    setIsChatting(true);
    setSources([]); // 清空之前的来源
    setCrossDocSources([]); // 清空跨文档来源
    clearSearchState(); // 清空搜索状态
    fullContentRef.current = '';
    displayedLenRef.current = 0;
    isDoneRef.current = false;
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    // 根据模式选择发送方式
    if (isCrossDocMode && selectedPaperIds.length > 0) {
      // 跨文档问答
      sendCrossDocMessage(trimmed, selectedPaperIds, sessionId);
    } else {
      // 单论文RAG问答
      sendRagMessage(trimmed, paperId, sessionId, null, enableSearch);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // 处理新建会话
  const handleNewSession = async () => {
    // 如果当前是跨文档模式，创建跨文档会话
    if (isCrossDocMode && selectedPaperIds.length > 0) {
      await createCrossDocSession(selectedPaperIds, '跨文档对话');
    } else {
      await createSession(paperId, '新对话');
    }
    fullContentRef.current = '';
    displayedLenRef.current = 0;
    isDoneRef.current = false;
  };

  // 处理添加论文到跨文档问答
  const handleAddPaper = () => {
    setShowPaperSelector(true);
  };

  // 处理论文选择器确认
  const handlePaperSelectorConfirm = async (selectedIds) => {
    if (selectedIds.length === 0) return;
    
    // 设置跨文档论文列表
    setCrossDocPapers(selectedIds);
    
    // 如果选择了多篇论文，创建跨文档会话
    if (selectedIds.length >= 1) {
      await createCrossDocSession(selectedIds, '跨文档对话');
    }
  };

  // 处理移除跨文档论文
  const handleRemovePaper = (paperIdToRemove) => {
    removePaperFromCrossDoc(paperIdToRemove);
  };

  // 处理清空跨文档论文
  const handleClearCrossDoc = () => {
    clearCrossDocPapers();
  };

  // 处理切换会话
  const handleSwitchSession = async (sessionId) => {
    if (sessionId === currentSessionId) return;
    setCurrentSession(sessionId);
    await fetchMessages(sessionId);
    fullContentRef.current = '';
    displayedLenRef.current = 0;
    isDoneRef.current = false;
  };

  // 处理删除会话
  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    if (window.confirm('确定要删除这个会话吗？')) {
      await deleteSession(sessionId);
    }
  };

  // 处理点击引用跳转到页面
  const handleSourceClick = (pages, paperId = null) => {
    // 如果是跨文档引用且需要切换论文
    if (paperId && paperId !== paperId && onSwitchPaper) {
      onSwitchPaper(paperId, pages[0]);
    } else if (pages && pages.length > 0 && onNavigateToPage) {
      onNavigateToPage(pages[0]);
    }
  };

  // 获取论文标题
  const getPaperTitle = (pid) => {
    const paper = papers.find(p => p.id === pid);
    return paper ? paper.title : `论文 ${pid}`;
  };

  // 渲染带引用标记的内容
  const renderContentWithCitations = (text) => {
    if (!text) return null;
    
    const parts = [];
    let key = 0;
    let lastIndex = 0;
    
    // 匹配跨文档引用格式 [论文X, p.Y] 或 [论文X,p.Y]
    const crossDocRegex = /\[论文(\d+)\s*,?\s*p\.(\d+)\]/g;
    // 匹配单论文引用格式 [p.X]
    const singleDocRegex = /\[p\.(\d+)\]/g;
    
    // 先尝试匹配跨文档格式
    let match;
    while ((match = crossDocRegex.exec(text)) !== null) {
      // 添加引用前的文本
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
    
    // 处理剩余文本中的单论文引用
    const remainingText = text.slice(lastIndex);
    let singleLastIndex = 0;
    
    while ((match = singleDocRegex.exec(remainingText)) !== null) {
      // 添加引用前的文本
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
    
    // 添加剩余文本
    if (singleLastIndex < remainingText.length) {
      parts.push(
        <span key={key++}>{renderMarkdown(remainingText.slice(singleLastIndex))}</span>
      );
    }
    
    return parts.length > 0 ? parts : renderMarkdown(text);
  };

  // 简单Markdown渲染：使用 MarkdownContent 组件
  const renderMarkdown = (text) => {
    if (!text) return null;
    return <MarkdownContent content={text} />;
  };

  // 格式化时间
  const formatTime = (timeStr) => {
    if (!timeStr) return '';
    const date = new Date(timeStr);
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  if (!pdfText && !paperId) {
    return (
      <div className={styles.empty}>
        <p>上传PDF后可以进行提问</p>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* 会话侧边栏 */}
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
        
        {/* 跨文档论文选择区域 */}
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
          
          {/* 已选论文列表 */}
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

      {/* 侧边栏切换按钮 */}
      <button
        className={styles.sidebarToggle}
        onClick={() => setSidebarOpen(!sidebarOpen)}
        title={sidebarOpen ? '收起侧边栏' : '展开侧边栏'}
      >
        {sidebarOpen ? '◀' : '▶'}
      </button>

      {/* 主聊天区域 */}
      <div className={styles.chatArea}>
        <div className={styles.messages}>
          {messages.length === 0 && (
            <div className={styles.welcome}>
              <p>💬 有什么问题？可以针对论文内容进行提问</p>
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
              
              {/* 显示引用来源（仅对最后一条助手消息） */}
              {msg.role === 'assistant' && 
               !isChatting && 
               index === messages.length - 1 && (
                <>
                  {/* 单论文引用来源 */}
                  {sources.length > 0 && !isCrossDocMode && (
                    <div className={styles.sources}>
                      <div className={styles.sourcesTitle}>引用来源：</div>
                      {sources.map((source, idx) => (
                        source.type === 'web' ? (
                          // 网络来源
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
                          // 论文来源
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
                  
                  {/* 跨文档引用来源 */}
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
        {/* 搜索控制面板 */}
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
            placeholder="输入你的问题..."
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
      
      {/* 论文选择器弹窗 */}
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

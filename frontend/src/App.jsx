import { useState, useCallback, useEffect, useRef, lazy, Suspense } from 'react';
import { Routes, Route, Navigate, useParams, useLocation, useNavigate } from 'react-router-dom';
// 核心阅读页面组件保持直接导入（核心页面性能考虑）
import FileUpload from './components/FileUpload/FileUpload';
import ExplanationPanel from './components/ExplanationPanel/ExplanationPanel';
import ChatPanel from './components/ChatPanel/ChatPanel';
import PDFReader from './components/PDFReader/PDFReader';
import NotePanel from './components/NotePanel/NotePanel';
import NoteEditor from './components/NoteEditor/NoteEditor';
import Recommendations from './components/Recommendations/Recommendations';
import Navbar from './components/Navbar/Navbar';
import useWebSocket from './hooks/useWebSocket';
import useTheme, { initializeTheme } from './hooks/useTheme';
import useAuthStore from './stores/authStore';
import usePaperStore from './stores/paperStore';
import useHighlightStore from './stores/highlightStore';
import useNoteStore from './stores/noteStore';
import useAgentStore from './stores/agentStore';
import useChatStore from './stores/chatStore';
import useSettingsStore from './stores/settingsStore';
import api from './api';
import './App.css';

// 初始化主题（在应用启动时立即应用，避免闪烁）
initializeTheme();

// 懒加载页面组件（代码分割）
const PaperList = lazy(() => import('./pages/PaperList'));
const WritingPage = lazy(() => import('./pages/WritingPage'));
const KnowledgePage = lazy(() => import('./pages/KnowledgePage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

// 页面加载中的 fallback 组件
const PageLoader = () => (
  <div style={{ 
    display: 'flex', 
    justifyContent: 'center', 
    alignItems: 'center', 
    height: '100vh',
    color: 'var(--color-text-secondary)',
    fontSize: '16px',
    background: 'var(--color-bg-primary)'
  }}>
    <div style={{ textAlign: 'center' }}>
      <div className="loading-spinner" style={{
        width: '40px',
        height: '40px',
        border: '3px solid var(--color-border)',
        borderTopColor: 'var(--color-accent)',
        borderRadius: '50%',
        animation: 'spin 1s linear infinite',
        margin: '0 auto 16px'
      }}></div>
      加载中...
    </div>
  </div>
);

// 阅读页面组件
function ReaderPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { 
    getPaperFileUrl, 
    fetchPaperText, 
    currentPaper, 
    fetchPaper,
    markAsReading,
    recommendations,
    recommendationsLoading,
    fetchRecommendations,
    clearRecommendations
  } = usePaperStore();
  
  // Agent 状态管理
  const {
    isAgentMode,
    startAgentMode,
    setIntent,
    setPlan,
    startStep,
    updateStepResult,
    appendAnswer,
    markComplete,
    setError: setAgentError,
    reset: resetAgent
  } = useAgentStore();
  const { 
    highlights, 
    activeHighlight, 
    fetchHighlights, 
    createHighlight, 
    deleteHighlight,
    setActiveHighlight,
    clearHighlights 
  } = useHighlightStore();
  const {
    notes,
    activeNote,
    fetchNotes,
    createNote,
    updateNote,
    deleteNote,
    setActiveNote,
    clearNotes
  } = useNoteStore();
  
  const [pdfUrl, setPdfUrl] = useState(null);
  const [pdfText, setPdfText] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [explanations, setExplanations] = useState([]);
  const [deepAnalysis, setDeepAnalysis] = useState({ dimensions: [], knowledgePoints: [] });
  const [chatMessages, setChatMessages] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isDeepAnalyzing, setIsDeepAnalyzing] = useState(false);
  const [isChatting, setIsChatting] = useState(false);
  const [keywords, setKeywords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // 笔记相关状态
  const [noteEditorOpen, setNoteEditorOpen] = useState(false);
  const [editingNote, setEditingNote] = useState(null);
  const [pendingHighlightForNote, setPendingHighlightForNote] = useState(null);
  const [activeTab, setActiveTab] = useState('explanation'); // 'explanation' | 'notes' | 'recommendations'
  const [explanationSubTab, setExplanationSubTab] = useState('overview'); // 'overview' | 'deep'

  // 三栏宽度状态（百分比）
  const [leftWidth, setLeftWidth] = useState(25);
  const [rightWidth, setRightWidth] = useState(25);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef(null);

  // 分析消息累积文本（用于流式解析）
  const analyzeTextRef = useRef('');
  const deepAnalyzeTextRef = useRef('');

  const { status: wsStatus, sendMessage, sendRagMessage, sendCrossDocMessage, onMessage } = useWebSocket();

  // ============ Agent 模式 WebSocket 消息处理 ============
  useEffect(() => {
    // 处理 Agent 相关的 WebSocket 消息
    const unsubscribe = onMessage((data) => {
      switch (data.type) {
        case 'agent_intent':
          // 意图识别结果
          setIntent(data.intent);
          break;
          
        case 'agent_plan':
          // 任务计划
          setPlan(data.plan);
          break;
          
        case 'agent_step':
          // 步骤开始
          if (data.step) {
            startStep(data.step);
          }
          break;
          
        case 'agent_step_result':
          // 步骤结果
          if (data.step && data.result) {
            updateStepResult(data.step, data.result);
          }
          break;
          
        case 'agent_answer_chunk':
          // 最终答案片段
          if (data.content) {
            appendAnswer(data.content);
          }
          break;
          
        case 'done':
          // 完成信号
          if (data.channel === 'agent_chat') {
            markComplete();
          }
          break;
          
        case 'error':
          // 错误处理
          setAgentError(data.message);
          break;
          
        default:
          // 其他消息类型由 ChatPanel 处理
          break;
      }
    });
    
    return () => unsubscribe();
  }, [onMessage, setIntent, setPlan, startStep, updateStepResult, appendAnswer, markComplete, setAgentError]);

  // ============ 分析相关 WebSocket 消息处理（提升到 ReaderPage 级别） ============
  useEffect(() => {
    // 解析章节概览 JSON 行
    const parseExplanations = (text) => {
      const results = [];
      const seen = new Set();
      const lines = text.split('\n');
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
          try {
            const obj = JSON.parse(trimmed);
            if (obj.section && obj.explanation) {
              const key = `${obj.section}::${obj.type || ''}`;
              if (!seen.has(key)) {
                seen.add(key);
                results.push(obj);
              }
            }
          } catch {
            // 不完整的JSON，跳过
          }
        }
      }
      return results;
    };

    // 解析深度分析 JSON 行
    const parseDeepAnalysis = (text) => {
      const dimensions = [];
      const knowledgePoints = [];
      const seenDimensions = new Set();
      const seenKnowledgePoints = new Set();
      
      const lines = text.split('\n');
      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
          try {
            const obj = JSON.parse(trimmed);
            if (obj.dimension && obj.content) {
              if (obj.dimension === 'knowledge_point') {
                const key = `${obj.title || ''}::${obj.content.slice(0, 50)}`;
                if (!seenKnowledgePoints.has(key)) {
                  seenKnowledgePoints.add(key);
                  knowledgePoints.push(obj);
                }
              } else {
                if (!seenDimensions.has(obj.dimension)) {
                  seenDimensions.add(obj.dimension);
                  dimensions.push(obj);
                }
              }
            }
          } catch {
            // 不完整的JSON，跳过
          }
        }
      }
      return { dimensions, knowledgePoints };
    };

    // 监听章节概览分析消息
    const unsubAnalyzeChunk = onMessage('analyze_chunk', (msg) => {
      analyzeTextRef.current += msg.data;
      const parsed = parseExplanations(analyzeTextRef.current);
      if (parsed.length > 0) {
        setExplanations([...parsed]);
      }
    });

    // 监听深度分析消息
    const unsubDeepChunk = onMessage('deep_analyze_chunk', (msg) => {
      deepAnalyzeTextRef.current += msg.data;
      const parsed = parseDeepAnalysis(deepAnalyzeTextRef.current);
      if (parsed.dimensions.length > 0 || parsed.knowledgePoints.length > 0) {
        setDeepAnalysis({ ...parsed });
      }
    });

    // 监听完成消息
    const unsubDone = onMessage('done', (msg) => {
      if (msg.channel === 'analyze') {
        setIsAnalyzing(false);
        const finalParsed = parseExplanations(analyzeTextRef.current);
        if (finalParsed.length > 0) {
          setExplanations([...finalParsed]);
        }
      } else if (msg.channel === 'deep_analyze') {
        setIsDeepAnalyzing(false);
        const finalParsed = parseDeepAnalysis(deepAnalyzeTextRef.current);
        setDeepAnalysis({ ...finalParsed });
      }
    });

    // 监听错误消息
    const unsubError = onMessage('error', (msg) => {
      console.error('分析错误:', msg.message);
      setIsAnalyzing(false);
      setIsDeepAnalyzing(false);
    });

    // 监听关键词提取结果
    const unsubKeywords = onMessage('keywords_result', (msg) => {
      if (msg.keywords && Array.isArray(msg.keywords)) {
        setKeywords(msg.keywords);
      }
    });

    return () => {
      unsubAnalyzeChunk();
      unsubDeepChunk();
      unsubDone();
      unsubError();
      unsubKeywords();
    };
  }, [onMessage, setExplanations, setDeepAnalysis, setIsAnalyzing, setIsDeepAnalyzing]);

  // 加载论文数据
  useEffect(() => {
    const loadPaper = async () => {
      setLoading(true);
      setError(null);
      try {
        // 获取论文详情
        const paper = await fetchPaper(id);
        
        // 异步标记为阅读中（不阻塞 UI）
        markAsReading(id).catch(err => {
          console.warn('标记阅读状态失败:', err);
        });
        
        // 设置 PDF URL
        setPdfUrl(getPaperFileUrl(id));
        
        // 获取全文文本
        const textData = await fetchPaperText(id);
        setPdfText(textData.text);
        
        // 加载分析缓存
        try {
          const res = await api.get(`/papers/${id}/analysis`);
          const cache = res.data;
          
          if (cache.has_section_analysis && cache.section_analysis) {
            // 解析流式 JSON 行
            const lines = cache.section_analysis.trim().split('\n');
            const parsed = lines
              .filter(line => line.trim().startsWith('{'))
              .map(line => { try { return JSON.parse(line); } catch { return null; } })
              .filter(Boolean);
            setExplanations(parsed);
          }
          
          if (cache.has_deep_analysis && cache.deep_analysis) {
            const lines = cache.deep_analysis.trim().split('\n');
            const dimensions = [];
            const knowledgePoints = [];
            lines.forEach(line => {
              try {
                const obj = JSON.parse(line.trim());
                if (obj.dimension === 'knowledge_point') {
                  knowledgePoints.push(obj);
                } else if (obj.dimension) {
                  dimensions.push(obj);
                }
              } catch {}
            });
            setDeepAnalysis({ dimensions, knowledgePoints });
          }
        } catch (err) {
          console.warn('加载分析缓存失败:', err);
        }
        
        // 加载已有关键词缓存
        if (paper.tags) {
          try {
            const tags = typeof paper.tags === 'string' ? JSON.parse(paper.tags) : paper.tags;
            if (Array.isArray(tags)) {
              setKeywords(tags);
            }
          } catch {}
        }
        
        // 加载高亮数据
        await fetchHighlights(id);
        
        // 加载笔记数据
        await fetchNotes(id);
        
        // 加载相似论文推荐
        fetchRecommendations(id).catch(err => {
          console.error('加载推荐失败:', err);
        });
        
        // 恢复阅读进度
        if (paper.last_read_page > 0) {
          setCurrentPage(paper.last_read_page);
        }
      } catch (err) {
        console.error('加载论文失败:', err);
        setError('加载论文失败，请重试');
      } finally {
        setLoading(false);
      }
    };
    
    if (id) {
      loadPaper();
    }
    
    // 清理（保留分析结果，以便返回页面时能恢复）
    return () => {
      setPdfUrl(null);
      setPdfText('');
      // 注意：不清空 explanations 和 deepAnalysis，保留分析结果
      setChatMessages([]);
      clearHighlights();
      clearNotes();
      clearRecommendations(); // 清理推荐数据
      resetAgent(); // 清理 Agent 状态
    };
  }, [id, fetchHighlights, clearHighlights, fetchNotes, clearNotes, clearRecommendations]);

  // 触发章节概述分析
  const handleOverviewAnalyze = useCallback(() => {
    if (!pdfText || pdfText.length < 50 || wsStatus !== 'connected') return;
    
    setExplanations([]);
    setIsAnalyzing(true);
    setExplanationSubTab('explanation');
    sendMessage('analyze', { text: pdfText, paper_id: parseInt(id) });
  }, [pdfText, wsStatus, sendMessage, id]);

  // 触发深度分析
  const handleDeepAnalyze = useCallback(() => {
    if (!pdfText || pdfText.length < 50 || wsStatus !== 'connected') return;
    
    setDeepAnalysis({ dimensions: [], knowledgePoints: [] });
    setIsDeepAnalyzing(true);
    setExplanationSubTab('deep');
    sendMessage('deep_analyze', { text: pdfText, paper_id: parseInt(id) });
  }, [pdfText, wsStatus, sendMessage, id]);

  // 拖拽调整面板宽度
  const handleMouseDown = useCallback((e, resizer) => {
    e.preventDefault();
    const startX = e.clientX;
    const containerWidth = containerRef.current.getBoundingClientRect().width;
    const startLeftWidth = leftWidth;
    const startRightWidth = rightWidth;

    setIsDragging(true);

    const handleMouseMove = (e) => {
      const delta = ((e.clientX - startX) / containerWidth) * 100;
      if (resizer === 'left') {
        const newLeft = Math.max(15, Math.min(50, startLeftWidth + delta));
        setLeftWidth(newLeft);
      } else {
        const newRight = Math.max(15, Math.min(50, startRightWidth - delta));
        setRightWidth(newRight);
      }
    };

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [leftWidth, rightWidth]);

  const handleTextSelected = useCallback((selectedText, rects, page) => {
    console.log('选中文本:', selectedText, '页面:', page, '位置:', rects);
  }, []);

  const handlePageChange = useCallback((pageNumber) => {
    setCurrentPage(pageNumber);
  }, []);

  // 处理创建高亮
  const handleCreateHighlight = useCallback(async (highlightData) => {
    try {
      await createHighlight(highlightData);
    } catch (err) {
      console.error('创建高亮失败:', err);
      alert('创建高亮失败，请重试');
    }
  }, [createHighlight]);

  // 处理点击高亮
  const handleHighlightClick = useCallback((highlight) => {
    setActiveHighlight(highlight);
  }, [setActiveHighlight]);

  // 处理删除高亮
  const handleDeleteHighlight = useCallback(async () => {
    if (!activeHighlight) return;
    try {
      await deleteHighlight(activeHighlight.id);
    } catch (err) {
      console.error('删除高亮失败:', err);
      alert('删除高亮失败，请重试');
    }
  }, [activeHighlight, deleteHighlight]);

  // ============ 笔记相关回调 ============
  
  // 处理从工具栏添加笔记（绑定高亮）
  const handleAddNoteFromToolbar = useCallback(() => {
    if (activeHighlight) {
      // 如果已有高亮被选中，绑定到该高亮
      setPendingHighlightForNote({
        highlightId: activeHighlight.id,
        highlightText: activeHighlight.selected_text
      });
    } else {
      // 否则创建独立笔记
      setPendingHighlightForNote(null);
    }
    setEditingNote(null);
    setNoteEditorOpen(true);
  }, [activeHighlight]);

  // 处理添加独立笔记
  const handleAddNote = useCallback(() => {
    setPendingHighlightForNote(null);
    setEditingNote(null);
    setNoteEditorOpen(true);
  }, []);

  // 处理编辑笔记
  const handleEditNote = useCallback((note) => {
    setEditingNote(note);
    setPendingHighlightForNote(note.highlight_id ? {
      highlightId: note.highlight_id,
      highlightText: note.highlight_text
    } : null);
    setNoteEditorOpen(true);
  }, []);

  // 处理保存笔记
  const handleSaveNote = useCallback(async (content) => {
    try {
      if (editingNote) {
        // 更新现有笔记
        await updateNote(editingNote.id, { content });
      } else {
        // 创建新笔记
        await createNote({
          paper_id: parseInt(id),
          highlight_id: pendingHighlightForNote?.highlightId || null,
          content
        });
      }
    } catch (err) {
      console.error('保存笔记失败:', err);
      alert('保存笔记失败，请重试');
      throw err;
    }
  }, [editingNote, pendingHighlightForNote, id, createNote, updateNote]);

  // 处理删除笔记
  const handleDeleteNote = useCallback(async (note) => {
    try {
      await deleteNote(note.id);
    } catch (err) {
      console.error('删除笔记失败:', err);
      alert('删除笔记失败，请重试');
    }
  }, [deleteNote]);

  // 处理点击笔记（跳转到对应高亮）
  const handleNoteClick = useCallback((note) => {
    setActiveNote(note);
    
    // 如果笔记关联了高亮，跳转到对应页面并选中高亮
    if (note.highlight_id) {
      const highlight = highlights.find(h => h.id === note.highlight_id);
      if (highlight) {
        setActiveHighlight(highlight);
        setCurrentPage(highlight.page);
      }
    }
  }, [highlights, setActiveHighlight]);

  // 处理关闭笔记编辑器
  const handleCloseNoteEditor = useCallback(() => {
    setNoteEditorOpen(false);
    setEditingNote(null);
    setPendingHighlightForNote(null);
  }, []);

  if (loading) {
    return (
      <div className="app app-with-navbar">
        <Navbar />
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>加载论文中...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="app app-with-navbar">
        <Navbar />
        <div className="error-container">
          <p>{error}</p>
          <button onClick={() => window.location.reload()}>重试</button>
        </div>
      </div>
    );
  }

  return (
    <div className="app app-with-navbar">
      <Navbar />
      <header className="app-header">
        <h1>PaperChat</h1>
        <div className="header-actions">
          <span className="filename">{currentPaper?.title || '未命名论文'}</span>
          <span className={`ws-status ws-status-${wsStatus}`} title={`WebSocket: ${wsStatus}`}>
            {wsStatus === 'connected' ? '●' : wsStatus === 'connecting' ? '◐' : '○'}
          </span>
          <button className="reset-btn" onClick={() => navigate('/papers')}>返回列表</button>
        </div>
      </header>
      <main className="three-column-layout" ref={containerRef}>
        <aside className="left-panel" style={{ width: `${leftWidth}%` }}>
          {/* Tab 切换 */}
          <div className="panel-tabs">
            <button 
              className={`panel-tab ${activeTab === 'explanation' ? 'active' : ''}`}
              onClick={() => setActiveTab('explanation')}
            >
              论文解析
            </button>
            <button 
              className={`panel-tab ${activeTab === 'notes' ? 'active' : ''}`}
              onClick={() => setActiveTab('notes')}
            >
              笔记
              {notes.length > 0 && <span className="tab-badge">{notes.length}</span>}
            </button>
            <button 
              className={`panel-tab ${activeTab === 'recommendations' ? 'active' : ''}`}
              onClick={() => setActiveTab('recommendations')}
            >
              推荐
              {recommendations.length > 0 && <span className="tab-badge">{recommendations.length}</span>}
            </button>
          </div>
          <div className="panel-content panel-content-no-padding">
            {activeTab === 'explanation' ? (
              <>
                {/* 分析按钮组 */}
                <div className="analyze-buttons">
                  <button 
                    className="analyze-btn overview-btn"
                    onClick={handleOverviewAnalyze}
                    disabled={isAnalyzing || !pdfText}
                    title="生成论文章节概述"
                  >
                    {isAnalyzing ? '分析中...' : '📖 章节概述'}
                  </button>
                  <button 
                    className="analyze-btn deep-btn"
                    onClick={handleDeepAnalyze}
                    disabled={isDeepAnalyzing || !pdfText}
                    title="生成6维度深度分析报告"
                  >
                    {isDeepAnalyzing ? '分析中...' : '🔬 深度分析'}
                  </button>
                </div>
                <ExplanationPanel
                  pdfText={pdfText}
                  explanations={explanations}
                  deepAnalysis={deepAnalysis}
                  isAnalyzing={isAnalyzing}
                  isDeepAnalyzing={isDeepAnalyzing}
                  keywords={keywords}
                />
              </>
            ) : activeTab === 'notes' ? (
              <NotePanel
                notes={notes}
                onNoteClick={handleNoteClick}
                onAddNote={handleAddNote}
                onEditNote={handleEditNote}
                onDeleteNote={handleDeleteNote}
                activeNoteId={activeNote?.id}
              />
            ) : (
              <div style={{ padding: '12px', height: '100%', overflow: 'auto' }}>
                <Recommendations
                  papers={recommendations}
                  title="相似论文推荐"
                  loading={recommendationsLoading}
                  layout="vertical"
                  collapsible={false}
                  onRefresh={() => fetchRecommendations(id)}
                  emptyText="上传更多论文以获取相似推荐"
                />
              </div>
            )}
          </div>
        </aside>
        <div
          className={`resizer ${isDragging ? 'resizer-active' : ''}`}
          onMouseDown={(e) => handleMouseDown(e, 'left')}
        />
        <section className="center-panel" style={{ width: `${100 - leftWidth - rightWidth}%` }}>
          <div className="panel-title">
            原文阅读
            {activeHighlight && (
              <button 
                className="delete-highlight-btn"
                onClick={handleDeleteHighlight}
                title="删除选中高亮"
              >
                删除高亮
              </button>
            )}
          </div>
          <div className="pdf-embed-container">
            {pdfUrl && (
              <>
                <PDFReader
                  file={pdfUrl}
                  onTextSelected={handleTextSelected}
                  onPageChange={handlePageChange}
                  onCreateHighlight={handleCreateHighlight}
                  onHighlightClick={handleHighlightClick}
                  onAddNote={handleAddNoteFromToolbar}
                  initialPage={currentPage}
                  highlights={highlights}
                  activeHighlight={activeHighlight}
                  paperId={parseInt(id)}
                />
                {isDragging && <div className="pdf-overlay" />}
              </>
            )}
          </div>
        </section>
        <div
          className={`resizer ${isDragging ? 'resizer-active' : ''}`}
          onMouseDown={(e) => handleMouseDown(e, 'right')}
        />
        <aside className="right-panel" style={{ width: `${rightWidth}%` }}>
          <div className="panel-title">智能问答</div>
          <div className="panel-content">
            <ChatPanel
              pdfText={pdfText}
              paperId={parseInt(id)}
              isChatting={isChatting}
              setIsChatting={setIsChatting}
              sendRagMessage={sendRagMessage}
              sendCrossDocMessage={sendCrossDocMessage}
              onMessage={onMessage}
              wsStatus={wsStatus}
              onNavigateToPage={setCurrentPage}
              onSwitchPaper={(newPaperId, page) => {
                // 切换到新论文并跳转到指定页面
                navigate(`/reader/${newPaperId}${page ? `?page=${page}` : ''}`);
              }}
            />
          </div>
        </aside>
      </main>
      
      {/* 笔记编辑器弹窗 */}
      <NoteEditor
        isOpen={noteEditorOpen}
        onClose={handleCloseNoteEditor}
        onSave={handleSaveNote}
        onDelete={editingNote ? () => handleDeleteNote(editingNote) : null}
        initialContent={editingNote?.content || ''}
        highlightText={pendingHighlightForNote?.highlightText || null}
        isEditing={!!editingNote}
      />
    </div>
  );
}

// 清理函数 - 组件卸载时重置 chat store
function useChatCleanup() {
  const { reset } = useChatStore();
  useEffect(() => {
    return () => reset();
  }, [reset]);
}

// 带导航栏的布局组件
function AppLayout({ children }) {
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <Navbar />
      <main style={{ flex: 1, marginLeft: '64px', overflowY: 'auto', minHeight: '100vh' }}>
        {children}
      </main>
    </div>
  );
}

// 主应用组件（原有的三栏布局）- 现在用于直接上传
function MainApp() {
  const [pdfFile, setPdfFile] = useState(null);
  const [pdfText, setPdfText] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [explanations, setExplanations] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isChatting, setIsChatting] = useState(false);

  // 三栏宽度状态（百分比）
  const [leftWidth, setLeftWidth] = useState(25);
  const [rightWidth, setRightWidth] = useState(25);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef(null);

  const { status: wsStatus, sendMessage, onMessage } = useWebSocket();

  // 拖拽调整面板宽度
  const handleMouseDown = useCallback((e, resizer) => {
    e.preventDefault();
    const startX = e.clientX;
    const containerWidth = containerRef.current.getBoundingClientRect().width;
    const startLeftWidth = leftWidth;
    const startRightWidth = rightWidth;

    setIsDragging(true);

    const handleMouseMove = (e) => {
      const delta = ((e.clientX - startX) / containerWidth) * 100;
      if (resizer === 'left') {
        const newLeft = Math.max(15, Math.min(50, startLeftWidth + delta));
        setLeftWidth(newLeft);
      } else {
        const newRight = Math.max(15, Math.min(50, startRightWidth - delta));
        setRightWidth(newRight);
      }
    };

    const handleMouseUp = () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      setIsDragging(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [leftWidth, rightWidth]);

  const handleFileSelect = useCallback((file) => {
    setPdfFile(file);
    // 重置状态
    setExplanations([]);
    setChatMessages([]);
    setPdfText('');
    setCurrentPage(1);
  }, []);

  const handleReset = () => {
    setPdfFile(null);
    setPdfText('');
    setExplanations([]);
    setChatMessages([]);
    setIsAnalyzing(false);
    setIsChatting(false);
    setCurrentPage(1);
  };

  const handleTextSelected = useCallback((selectedText, rects, page) => {
    console.log('选中文本:', selectedText, '页面:', page, '位置:', rects);
  }, []);

  const handlePageChange = useCallback((pageNumber) => {
    setCurrentPage(pageNumber);
  }, []);

  // 如果还没上传文件，显示上传界面
  if (!pdfFile) {
    return (
      <div className="app">
        <header className="app-header">
          <h1>PaperChat</h1>
          <p className="app-subtitle">智能论文分析系统</p>
        </header>
        <main className="app-upload">
          <FileUpload onFileSelect={handleFileSelect} />
        </main>
      </div>
    );
  }

  // 三栏布局
  return (
    <div className="app">
      <header className="app-header">
        <h1>PaperChat</h1>
        <div className="header-actions">
          <span className="filename">{pdfFile.name}</span>
          <span className={`ws-status ws-status-${wsStatus}`} title={`WebSocket: ${wsStatus}`}>
            {wsStatus === 'connected' ? '●' : wsStatus === 'connecting' ? '◐' : '○'}
          </span>
          <button className="reset-btn" onClick={handleReset}>重新上传</button>
        </div>
      </header>
      <main className="three-column-layout" ref={containerRef}>
        <aside className="left-panel" style={{ width: `${leftWidth}%` }}>
          <div className="panel-title">论文解析</div>
          <div className="panel-content panel-content-no-padding">
            <ExplanationPanel
              pdfText={pdfText}
              explanations={explanations}
              isAnalyzing={isAnalyzing}
            />
          </div>
        </aside>
        <div
          className={`resizer ${isDragging ? 'resizer-active' : ''}`}
          onMouseDown={(e) => handleMouseDown(e, 'left')}
        />
        <section className="center-panel" style={{ width: `${100 - leftWidth - rightWidth}%` }}>
          <div className="panel-title">原文阅读</div>
          <div className="pdf-embed-container">
            {pdfFile && (
              <>
                <PDFReader
                  file={pdfFile}
                  onTextSelected={handleTextSelected}
                  onPageChange={handlePageChange}
                  initialPage={currentPage}
                />
                {isDragging && <div className="pdf-overlay" />}
              </>
            )}
          </div>
        </section>
        <div
          className={`resizer ${isDragging ? 'resizer-active' : ''}`}
          onMouseDown={(e) => handleMouseDown(e, 'right')}
        />
        <aside className="right-panel" style={{ width: `${rightWidth}%` }}>
          <div className="panel-title">智能问答</div>
          <div className="panel-content">
            <ChatPanel
              pdfText={pdfText}
              chatMessages={chatMessages}
              setChatMessages={setChatMessages}
              isChatting={isChatting}
              setIsChatting={setIsChatting}
              sendMessage={sendMessage}
              onMessage={onMessage}
              wsStatus={wsStatus}
            />
          </div>
        </aside>
      </main>
    </div>
  );
}

// 路由配置组件
function App() {
  const { initialize } = useAuthStore();
  const fetchSettings = useSettingsStore(state => state.fetchSettings);

  // 应用主题
  useTheme();

  // 初始化认证状态
  useEffect(() => {
    initialize();
  }, [initialize]);

  // 加载设置（包含主题等外观配置）
  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  return (
    <Routes>
      {/* 论文列表页 */}
      <Route
        path="/papers"
        element={
          <AppLayout>
            <Suspense fallback={<PageLoader />}>
              <PaperList />
            </Suspense>
          </AppLayout>
        }
      />
      
      {/* 阅读页面 - 核心页面保持直接加载，不显示导航栏 */}
      <Route
        path="/reader/:id"
        element={
          <ReaderPage />
        }
      />

      {/* 知识库页面 */}
      <Route
        path="/knowledge"
        element={
          <AppLayout>
            <Suspense fallback={<PageLoader />}>
              <KnowledgePage />
            </Suspense>
          </AppLayout>
        }
      />


      {/* 写作辅助页面 */}
      <Route
        path="/writing"
        element={
          <AppLayout>
            <Suspense fallback={<PageLoader />}>
              <WritingPage />
            </Suspense>
          </AppLayout>
        }
      />

      {/* 设置页面 */}
      <Route
        path="/settings"
        element={
          <AppLayout>
            <Suspense fallback={<PageLoader />}>
              <SettingsPage />
            </Suspense>
          </AppLayout>
        }
      />
      
      {/* 原有主页（直接上传） */}
      <Route
        path="/"
        element={
          <Navigate to="/papers" replace />
        }
      />
      
      {/* 404 页面 */}
      <Route path="*" element={
        <Suspense fallback={<PageLoader />}>
          <NotFoundPage />
        </Suspense>
      } />
    </Routes>
  );
}

export default App;

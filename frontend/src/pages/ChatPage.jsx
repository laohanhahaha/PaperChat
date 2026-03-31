import { useState, useEffect, useCallback } from 'react';
import usePaperStore from '../stores/paperStore';
import useChatStore from '../stores/chatStore';
import ChatPanel from '../components/ChatPanel/ChatPanel';
import PaperSelector from '../components/PaperSelector/PaperSelector';
import useWebSocket from '../hooks/useWebSocket';
import styles from './ChatPage.module.css';

function ChatPage() {
    const { papers, fetchPapers } = usePaperStore();
    const {
        sessions,
        currentSessionId,
        fetchSessions,
        setCurrentSession,
        deleteSession
    } = useChatStore();

    const [selectedPaperId, setSelectedPaperId] = useState(null);
    const [selectedPaperIds, setSelectedPaperIds] = useState([]);
    const [showPaperSelector, setShowPaperSelector] = useState(false);
    const [isChatting, setIsChatting] = useState(false);
    const [pdfText, setPdfText] = useState('');
    const { status: wsStatus, sendUnifiedChatMessage, onMessage } = useWebSocket();

    useEffect(() => {
        fetchPapers({ page: 1, page_size: 100 });
        fetchSessions();
    }, [fetchPapers, fetchSessions]);

    const handlePaperSelect = (paper) => {
        setSelectedPaperId(paper.id);
        setPdfText(paper.full_text || paper.text || '');
    };

    const handleMultiPaperSelect = (selectedIds) => {
        setSelectedPaperIds(selectedIds);
        if (selectedIds.length === 1) {
            const paper = papers.find(p => p.id === selectedIds[0]);
            if (paper) {
                setSelectedPaperId(selectedIds[0]);
                setPdfText(paper.full_text || paper.text || '');
            }
        } else {
            setSelectedPaperId(null);
            setPdfText('');
        }
        setShowPaperSelector(false);
    };

    const handleSendUnifiedChat = useCallback((message, paperId, paperIds, sessionId, enableSearch) => {
        if (wsStatus !== 'connected') return;
        sendUnifiedChatMessage(message, paperId, paperIds, sessionId, enableSearch);
    }, [wsStatus, sendUnifiedChatMessage]);

    const handleSwitchSession = async (sessionId) => {
        if (sessionId === currentSessionId) return;
        setCurrentSession(sessionId);
    };

    const handleDeleteSession = async (e, sessionId) => {
        e.stopPropagation();
        if (window.confirm('确定要删除这个会话吗？')) {
            await deleteSession(sessionId);
        }
    };

    const getPaperTitle = (pid) => {
        const paper = papers.find(p => p.id === pid);
        return paper ? paper.title : `论文 ${pid}`;
    };

    const formatTime = (timeStr) => {
        if (!timeStr) return '';
        const date = new Date(timeStr);
        return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    };

    const recentPapers = papers.slice(0, 5);

    return (
        <div className={styles.container}>
            <header className={styles.header}>
                <div className={styles.headerLeft}>
                    <h1 className={styles.title}>💬 统一聊天</h1>
                    <span className={styles.wsStatus}>
                        {wsStatus === 'connected' ? '● 已连接' : wsStatus === 'connecting' ? '◐ 连接中' : '○ 未连接'}
                    </span>
                </div>
                <div className={styles.headerRight}>
                    <button
                        className={styles.selectPaperBtn}
                        onClick={() => setShowPaperSelector(true)}
                    >
                        📚 选择论文
                    </button>
                </div>
            </header>

            {selectedPaperIds.length > 0 && (
                <div className={styles.selectedPapersBar}>
                    <span className={styles.selectedLabel}>已选论文：</span>
                    <div className={styles.selectedTags}>
                        {selectedPaperIds.map(pid => (
                            <span key={pid} className={styles.selectedTag}>
                                {getPaperTitle(pid).slice(0, 20)}
                                {getPaperTitle(pid).length > 20 ? '...' : ''}
                                <button
                                    className={styles.removeTag}
                                    onClick={() => {
                                        const newIds = selectedPaperIds.filter(id => id !== pid);
                                        handleMultiPaperSelect(newIds);
                                    }}
                                >
                                    ×
                                </button>
                            </span>
                        ))}
                    </div>
                </div>
            )}

            <div className={styles.content}>
                <aside className={styles.sidebar}>
                    <div className={styles.sidebarSection}>
                        <h3 className={styles.sidebarTitle}>最近论文</h3>
                        <div className={styles.paperList}>
                            {recentPapers.map(paper => (
                                <div
                                    key={paper.id}
                                    className={`${styles.paperItem} ${selectedPaperId === paper.id ? styles.active : ''}`}
                                    onClick={() => handlePaperSelect(paper)}
                                >
                                    <span className={styles.paperIcon}>📄</span>
                                    <span className={styles.paperName} title={paper.title}>
                                        {paper.title.slice(0, 15)}
                                        {paper.title.length > 15 ? '...' : ''}
                                    </span>
                                </div>
                            ))}
                            {recentPapers.length === 0 && (
                                <div className={styles.emptyHint}>暂无论文，请先上传</div>
                            )}
                        </div>
                    </div>

                    <div className={styles.sidebarSection}>
                        <h3 className={styles.sidebarTitle}>聊天历史</h3>
                        <div className={styles.sessionList}>
                            {sessions.map(session => (
                                <div
                                    key={session.id}
                                    className={`${styles.sessionItem} ${session.id === currentSessionId ? styles.active : ''}`}
                                    onClick={() => handleSwitchSession(session.id)}
                                >
                                    <div className={styles.sessionInfo}>
                                        <span className={styles.sessionTitle}>
                                            {session.is_cross_doc && <span className={styles.crossBadge}>跨</span>}
                                            {session.title.slice(0, 15)}
                                            {session.title.length > 15 ? '...' : ''}
                                        </span>
                                        <span className={styles.sessionTime}>
                                            {formatTime(session.updated_at)}
                                        </span>
                                    </div>
                                    <button
                                        className={styles.deleteBtn}
                                        onClick={(e) => handleDeleteSession(e, session.id)}
                                    >
                                        ×
                                    </button>
                                </div>
                            ))}
                            {sessions.length === 0 && (
                                <div className={styles.emptyHint}>暂无聊天记录</div>
                            )}
                        </div>
                    </div>
                </aside>

                <main className={styles.chatArea}>
                    {!selectedPaperId && selectedPaperIds.length === 0 ? (
                        <div className={styles.welcome}>
                            <div className={styles.welcomeContent}>
                                <h2>🔍 统一智能助手</h2>
                                <p className={styles.welcomeDesc}>选择一个论文开始智能问答</p>
                                <div className={styles.features}>
                                    <div className={styles.featureItem}>
                                        <span className={styles.featureIcon}>📋</span>
                                        <span>输入"章节概述"分析论文结构</span>
                                    </div>
                                    <div className={styles.featureItem}>
                                        <span className={styles.featureIcon}>🔬</span>
                                        <span>输入"深度分析"深入研究</span>
                                    </div>
                                    <div className={styles.featureItem}>
                                        <span className={styles.featureIcon}>🎯</span>
                                        <span>输入"核心知识点"提取重点</span>
                                    </div>
                                    <div className={styles.featureItem}>
                                        <span className={styles.featureIcon}>📚</span>
                                        <span>选择多篇论文进行跨文档分析</span>
                                    </div>
                                    <div className={styles.featureItem}>
                                        <span className={styles.featureIcon}>💬</span>
                                        <span>直接提问进行智能 RAG 问答</span>
                                    </div>
                                </div>
                                <button
                                    className={styles.startBtn}
                                    onClick={() => setShowPaperSelector(true)}
                                >
                                    选择论文开始聊天
                                </button>
                            </div>
                        </div>
                    ) : (
                        <ChatPanel
                            pdfText={pdfText}
                            paperId={selectedPaperId}
                            selectedPaperIds={selectedPaperIds}
                            isChatting={isChatting}
                            setIsChatting={setIsChatting}
                            sendUnifiedChatMessage={handleSendUnifiedChat}
                            onMessage={onMessage}
                            wsStatus={wsStatus}
                        />
                    )}
                </main>
            </div>

            <PaperSelector
                isOpen={showPaperSelector}
                onClose={() => setShowPaperSelector(false)}
                onConfirm={handleMultiPaperSelect}
                initialSelectedIds={selectedPaperIds}
                maxSelection={10}
            />
        </div>
    );
}

export default ChatPage;
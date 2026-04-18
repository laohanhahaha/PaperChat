import { useState, useCallback } from 'react';

/**
 * 会话管理 Hook
 * 封装会话 CRUD 操作和标题编辑逻辑
 *
 * @param {Object} params
 * @param {boolean} params.isChatting - 是否正在聊天
 * @param {boolean} params.isCrossDocMode - 是否跨文档模式
 * @param {Array} params.selectedPaperIds - 跨文档选中的论文 ID 列表
 * @param {string|null} params.selectedPaperId - 单文档选中的论文 ID
 * @param {string|null} params.currentSessionId - 当前会话 ID
 * @param {Function} params.handleStop - 停止当前聊天的函数
 * @param {Function} params.resetStreamState - 重置流状态的函数
 * @param {Function} params.createCrossDocSession - 创建跨文档会话
 * @param {Function} params.createSession - 创建普通会话
 * @param {Function} params.setCurrentSession - 设置当前会话
 * @param {Function} params.fetchMessages - 获取会话消息
 * @param {Function} params.deleteSession - 删除会话
 * @param {Function} params.renameSession - 重命名会话
 */
export function useSessionManager({
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
}) {
  const [editingSessionId, setEditingSessionId] = useState(null);
  const [editingTitle, setEditingTitle] = useState('');

  const handleNewSession = useCallback(async () => {
    if (isChatting) handleStop();
    if (isCrossDocMode && selectedPaperIds.length > 0) {
      await createCrossDocSession(selectedPaperIds, '跨文档对话');
    } else {
      await createSession(selectedPaperId, '新对话');
    }
    resetStreamState();
  }, [isChatting, handleStop, isCrossDocMode, selectedPaperIds, createCrossDocSession, selectedPaperId, createSession, resetStreamState]);

  const handleSwitchSession = useCallback(async (sessionId) => {
    if (sessionId === currentSessionId) return;
    if (isChatting) handleStop();
    resetStreamState();
    setCurrentSession(sessionId);
    await fetchMessages(sessionId, true); // true = reset and fetch from beginning
  }, [currentSessionId, isChatting, handleStop, resetStreamState, setCurrentSession, fetchMessages]);

  const handleDeleteSession = useCallback(async (e, sessionId) => {
    e.stopPropagation();
    if (window.confirm('确定要删除这个会话吗？')) {
      if (sessionId === currentSessionId && isChatting) handleStop();
      await deleteSession(sessionId);
    }
  }, [currentSessionId, isChatting, handleStop, deleteSession]);

  const handleStartEditing = useCallback((e, session) => {
    e.stopPropagation();
    setEditingSessionId(session.id);
    setEditingTitle(session.title);
  }, []);

  const handleSaveTitle = useCallback(async () => {
    if (!editingSessionId) return;
    const trimmedTitle = editingTitle.trim();
    if (trimmedTitle) {
      await renameSession(editingSessionId, trimmedTitle);
    }
    setEditingSessionId(null);
    setEditingTitle('');
  }, [editingSessionId, editingTitle, renameSession]);

  const handleCancelEditing = useCallback(() => {
    setEditingSessionId(null);
    setEditingTitle('');
  }, []);

  const handleEditKeyDown = useCallback((e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleSaveTitle();
    } else if (e.key === 'Escape') {
      handleCancelEditing();
    }
  }, [handleSaveTitle, handleCancelEditing]);

  return {
    handleNewSession,
    handleSwitchSession,
    handleDeleteSession,
    handleStartEditing,
    handleSaveTitle,
    handleCancelEditing,
    handleEditKeyDown,
    editingSessionId,
    editingTitle,
    setEditingTitle,
  };
}

export default useSessionManager;

import { useState, useEffect } from 'react';

/**
 * 聊天消息 WebSocket 监听 Hook
 * 统一管理 WebSocket 消息订阅，处理流式内容、意图检测、来源等
 *
 * @param {Object} params
 * @param {Function} params.onMessage - WebSocket 消息订阅函数
 * @param {Object} params.typewriter - useTypewriter 返回的打字机实例
 * @param {React.RefObject} [params.isChattingRef] - 可选，聊天状态 ref，提供时仅在聊天中接受 chunk
 * @param {React.RefObject} params.currentSessionIdRef - 当前会话 ID ref
 * @param {Function} params.setSources - 设置引用来源
 * @param {Function} params.setCrossDocSources - 设置跨文档引用来源
 * @param {Function} params.setSearchStatus - 设置搜索状态
 * @param {Function} params.updateLastMessage - 更新最后一条消息
 * @param {Function} params.setCurrentSession - 设置当前会话
 * @param {Function} [params.fetchSessions] - 可选，刷新会话列表（会话 ID 变化时调用）
 * @param {Function} [params.onError] - 可选，自定义错误处理
 * @param {Function} [params.onCancelled] - 可选，自定义取消处理
 * @param {Function} [params.resetStreamState] - 可选，默认错误处理中重置流状态
 */
export function useChatMessages({
  onMessage,
  typewriter,
  isChattingRef,
  currentSessionIdRef,
  setSources,
  setCrossDocSources,
  setSearchStatus,
  updateLastMessage,
  setCurrentSession,
  fetchSessions,
  onError,
  onCancelled,
  resetStreamState,
}) {
  const [currentIntent, setCurrentIntent] = useState(null);

  useEffect(() => {
    const shouldAccept = () => !isChattingRef || isChattingRef.current;

    const unsubs = [
      onMessage('rag_chat_chunk', (msg) => {
        if (!shouldAccept()) return;
        typewriter.appendContent(msg.content);
      }),
      onMessage('rag_sources', (msg) => { setSources(msg.sources || []); }),
      onMessage('cross_doc_chunk', (msg) => {
        if (!shouldAccept()) return;
        typewriter.appendContent(msg.content);
      }),
      onMessage('cross_doc_sources', (msg) => { setCrossDocSources(msg.sources || []); }),
      onMessage('search_status', (msg) => { setSearchStatus(msg.status); }),
      onMessage('analyze_chunk', (msg) => {
        if (!shouldAccept()) return;
        typewriter.appendContent(msg.data);
      }),
      onMessage('deep_analyze_chunk', (msg) => {
        if (!shouldAccept()) return;
        typewriter.appendContent(msg.data);
      }),
      onMessage('intent_detected', (msg) => {
        setCurrentIntent({ intent: msg.intent, tool: msg.tool, confidence: msg.confidence, matched: msg.matched });
      }),
      onMessage('done', (msg) => {
        if (['rag_chat', 'cross_doc_chat', 'analyze', 'deep_analyze'].includes(msg.channel)) {
          typewriter.markDone();
          if (msg.session_id) {
            const changed = msg.session_id !== currentSessionIdRef.current;
            currentSessionIdRef.current = msg.session_id;
            setCurrentSession(msg.session_id);
            if (changed && fetchSessions) {
              fetchSessions();
            }
          }
        }
      }),
    ];

    if (onCancelled) {
      unsubs.push(onMessage('cancelled', onCancelled));
    }

    if (onError) {
      unsubs.push(onMessage('error', onError));
    } else {
      unsubs.push(onMessage('error', (msg) => {
        console.error('问答错误:', msg.message);
        updateLastMessage(msg.message || '请求失败，请重试。');
        resetStreamState?.();
      }));
    }

    return () => {
      unsubs.forEach(fn => fn());
    };
  }, [onMessage, typewriter, isChattingRef, setSources, setCrossDocSources, setSearchStatus, updateLastMessage, setCurrentSession, fetchSessions, onError, onCancelled, resetStreamState, currentSessionIdRef]);

  return { currentIntent, setCurrentIntent };
}

export default useChatMessages;

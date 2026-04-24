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
 * @param {Function} [params.setLastMessageToolResult] - 可选，设置最后一条消息的工具结果
 * @param {Function} [params.addAgentStep] - 可选，向最后一条 assistant 消息追加 agent 步骤
 * @param {Function} [params.appendThinkingContent] - 可选，追加深度思考内容
 * @param {Function} [params.markAgentComplete] - 可选，标记 Agent 推理完成
 * @param {Function} params.setCurrentSession - 设置当前会话
 * @param {Function} [params.fetchSessions] - 可选，刷新会话列表（会话 ID 变化时调用）
 * @param {Function} [params.onError] - 可选，自定义错误处理
 * @param {Function} [params.onCancelled] - 可选，自定义取消处理
 * @param {Function} [params.onConfigUpdate] - 可选，配置变更回调（收到 config_update 事件时调用）
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
  setLastMessageToolResult,
  addAgentStep,
  appendThinkingContent,
  markAgentComplete,
  setCurrentSession,
  fetchSessions,
  onError,
  onCancelled,
  onConfigUpdate,
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
      onMessage('tool_result', (msg) => {
        // 工具结果：将结构化数据附加到最后一条 assistant 消息
        if (setLastMessageToolResult) {
          setLastMessageToolResult({
            tool: msg.tool,
            resultType: msg.result_type,
            content: msg.content,
          });
        }
      }),
      onMessage('intent_detected', (msg) => {
        setCurrentIntent({ intent: msg.intent, tool: msg.tool, confidence: msg.confidence, matched: msg.matched });
      }),

      // 深度思考事件
      onMessage('thinking_chunk', (msg) => {
        if (appendThinkingContent) appendThinkingContent(msg.content || '');
      }),
      onMessage('thinking_done', () => {
        // 思考结束，可扩展处理
      }),

      // Agent 推理事件
      onMessage('agent_thought', (msg) => {
        if (addAgentStep) addAgentStep({ type: 'agent_thought', step: msg.step || 0, content: msg.content, subAgent: msg.sub_agent || msg.subAgent });
      }),
      onMessage('agent_action', (msg) => {
        if (addAgentStep) addAgentStep({ type: 'agent_action', step: msg.step || 0, tool: msg.tool, input: msg.input, subAgent: msg.sub_agent || msg.subAgent });
      }),
      onMessage('agent_observation', (msg) => {
        if (addAgentStep) addAgentStep({ type: 'agent_observation', step: msg.step || 0, content: msg.content, subAgent: msg.sub_agent || msg.subAgent });
      }),
      onMessage('agent_reflection', (msg) => {
        if (addAgentStep) addAgentStep({ type: 'reflection', content: msg.content, subAgent: msg.sub_agent || msg.subAgent });
      }),
      onMessage('agent_final', () => {
        if (markAgentComplete) markAgentComplete();
      }),

      // 配置变更事件
      onMessage('config_update', (msg) => {
        if (onConfigUpdate) onConfigUpdate(msg);
      }),

      onMessage('done', (msg) => {
        if (['rag_chat', 'agent_chat', 'cross_doc_chat', 'analyze', 'deep_analyze'].includes(msg.channel)) {
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
  }, [onMessage, typewriter, isChattingRef, setSources, setCrossDocSources, setSearchStatus, updateLastMessage, setLastMessageToolResult, addAgentStep, appendThinkingContent, markAgentComplete, setCurrentSession, fetchSessions, onError, onCancelled, onConfigUpdate, resetStreamState, currentSessionIdRef]);

  return { currentIntent, setCurrentIntent };
}

export default useChatMessages;

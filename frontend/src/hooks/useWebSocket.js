import { useState, useEffect, useRef, useCallback } from 'react';

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
const MAX_RETRIES = 5;
const RETRY_DELAY = 3000;

export default function useWebSocket() {
  const [status, setStatus] = useState('disconnected'); // connecting | connected | disconnected
  const wsRef = useRef(null);
  const handlersRef = useRef(new Map());
  const retryCountRef = useRef(0);
  const retryTimerRef = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    
    setStatus('connecting');
    const ws = new WebSocket(WS_URL);
    
    ws.onopen = () => {
      setStatus('connected');
      retryCountRef.current = 0;
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const type = data.type;
        // 调用所有注册了该类型的处理器
        const handlers = handlersRef.current.get(type) || [];
        handlers.forEach(handler => handler(data));
        
        // 也调用通配符处理器
        const wildcard = handlersRef.current.get('*') || [];
        wildcard.forEach(handler => handler(data));
      } catch (err) {
        console.error('WebSocket message parse error:', err);
      }
    };
    
    ws.onclose = () => {
      setStatus('disconnected');
      wsRef.current = null;
      
      // 自动重连
      if (retryCountRef.current < MAX_RETRIES) {
        retryCountRef.current++;
        retryTimerRef.current = setTimeout(connect, RETRY_DELAY);
      }
    };
    
    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
    };
    
    wsRef.current = ws;
  }, []);

  // 组件挂载时自动连接
  useEffect(() => {
    connect();
    return () => {
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  // 发送消息
  const sendMessage = useCallback((type, payload = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, ...payload }));
      return true;
    }
    console.warn('WebSocket not connected, cannot send message');
    return false;
  }, []);

  // 发送RAG问答消息（带会话信息）
  const sendRagMessage = useCallback((message, paperId, sessionId = null, userId = null, enableSearch = false) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'rag_chat',
        message,
        paper_id: paperId,
        session_id: sessionId,
        user_id: userId || 1,
        enable_search: enableSearch
      }));
      return true;
    }
    console.warn('WebSocket not connected, cannot send message');
    return false;
  }, []);

  // 发送跨文档问答消息（带会话信息）
  const sendCrossDocMessage = useCallback((message, paperIds, sessionId = null, userId = null) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'cross_doc_chat',
        message,
        paper_ids: paperIds,
        session_id: sessionId,
        user_id: userId || 1
      }));
      return true;
    }
    console.warn('WebSocket not connected, cannot send message');
    return false;
  }, []);

  // 注册消息处理器，返回取消注册函数
  const onMessage = useCallback((type, handler) => {
    if (!handlersRef.current.has(type)) {
      handlersRef.current.set(type, []);
    }
    handlersRef.current.get(type).push(handler);
    
    // 返回取消注册函数
    return () => {
      const handlers = handlersRef.current.get(type) || [];
      const idx = handlers.indexOf(handler);
      if (idx !== -1) handlers.splice(idx, 1);
    };
  }, []);

  return { status, sendMessage, sendRagMessage, sendCrossDocMessage, onMessage, connect };
}

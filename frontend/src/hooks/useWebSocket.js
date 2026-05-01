import { useEffect, useCallback, useSyncExternalStore } from 'react';
import offlineQueue from '../services/offlineQueue';

const WS_URL = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
const MAX_RETRIES = 5;
const RETRY_DELAY = 3000;

let globalWs = null;
let globalStatus = 'disconnected';
let globalRetryCount = 0;
let globalRetryTimer = null;
const globalHandlers = new Map();
const statusListeners = new Set();

function notifyStatusChange(newStatus) {
  globalStatus = newStatus;
  statusListeners.forEach(fn => fn());
}

function globalConnect() {
  if (globalWs?.readyState === WebSocket.OPEN || globalWs?.readyState === WebSocket.CONNECTING) return;

  notifyStatusChange('connecting');
  const token = localStorage.getItem('token');
  const wsUrl = token ? `${WS_URL}?token=${token}` : WS_URL;
  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    globalRetryCount = 0;
    notifyStatusChange('connected');
    // 网络恢复后重放离线队列中的消息
    if (offlineQueue.size > 0) {
      offlineQueue.replayAll(async (item) => {
        if (globalWs?.readyState === WebSocket.OPEN) {
          const { id, timestamp, ...payload } = item;
          globalWs.send(JSON.stringify(payload));
        }
      }).then(results => {
        console.log('离线队列重放完成:', results);
      }).catch(err => {
        console.error('离线队列重放出错:', err);
      });
    }
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      const type = data.type;
      const handlers = globalHandlers.get(type) || [];
      handlers.forEach(handler => handler(data));
      const wildcard = globalHandlers.get('*') || [];
      wildcard.forEach(handler => handler(data));
    } catch (err) {
      console.error('WebSocket message parse error:', err);
    }
  };

  ws.onclose = () => {
    globalWs = null;
    notifyStatusChange('disconnected');
    if (globalRetryCount < MAX_RETRIES) {
      globalRetryCount++;
      globalRetryTimer = setTimeout(globalConnect, RETRY_DELAY);
    }
  };

  ws.onerror = (err) => {
    console.error('WebSocket error:', err);
  };

  globalWs = ws;
}

function globalDisconnect() {
  if (globalRetryTimer) {
    clearTimeout(globalRetryTimer);
    globalRetryTimer = null;
  }
  if (globalWs) {
    globalWs.close();
    globalWs = null;
  }
  notifyStatusChange('disconnected');
}

let refCount = 0;

function subscribeStatus(listener) {
  statusListeners.add(listener);
  return () => statusListeners.delete(listener);
}

function getStatusSnapshot() {
  return globalStatus;
}

export default function useWebSocket() {
  const status = useSyncExternalStore(subscribeStatus, getStatusSnapshot);

  useEffect(() => {
    refCount++;
    if (refCount === 1) {
      globalConnect();
    }
    return () => {
      refCount--;
      if (refCount === 0) {
        globalDisconnect();
      }
    };
  }, []);

  const sendMessage = useCallback((type, payload = {}) => {
    if (globalWs?.readyState === WebSocket.OPEN) {
      globalWs.send(JSON.stringify({ type, ...payload }));
      return true;
    }
    console.warn('WebSocket not connected, cannot send message');
    return false;
  }, []);

  const sendRagMessage = useCallback((message, paperId, sessionId = null, userId = null, enableSearch = false) => {
    const payload = {
      type: 'rag_chat',
      message,
      paper_id: paperId,
      session_id: sessionId,
      user_id: userId || 1,
      enable_search: enableSearch
    };
    // 离线或 WS 断连时入离线队列
    if (!navigator.onLine || globalWs?.readyState !== WebSocket.OPEN) {
      offlineQueue.enqueue(payload);
      console.warn(navigator.onLine ? 'WS 断连，消息已缓存' : '离线状态，消息已缓存到离线队列');
      return false;
    }
    globalWs.send(JSON.stringify(payload));
    return true;
  }, []);

  const sendCrossDocMessage = useCallback((message, paperIds, sessionId = null, userId = null) => {
    const payload = {
      type: 'cross_doc_chat',
      message,
      paper_ids: paperIds,
      session_id: sessionId,
      user_id: userId || 1
    };
    // 离线或 WS 断连时入离线队列
    if (!navigator.onLine || globalWs?.readyState !== WebSocket.OPEN) {
      offlineQueue.enqueue(payload);
      console.warn(navigator.onLine ? 'WS 断连，消息已缓存' : '离线状态，消息已缓存到离线队列');
      return false;
    }
    globalWs.send(JSON.stringify(payload));
    return true;
  }, []);

  const sendUnifiedChatMessage = useCallback((message, paperId = null, paperIds = [], sessionId = null, enableSearch = false, images = [], functionTool = null) => {
    const payload = {
      type: 'unified_chat',
      message,
      paper_id: paperId,
      paper_ids: paperIds || [],
      session_id: sessionId,
      enable_search: enableSearch,
      images: images || [],
    };
    if (functionTool) {
      payload.forced_tool = functionTool;
    }
    // 离线或 WS 断连时入离线队列
    if (!navigator.onLine || globalWs?.readyState !== WebSocket.OPEN) {
      offlineQueue.enqueue(payload);
      console.warn(navigator.onLine ? 'WS 断连，消息已缓存' : '离线状态，消息已缓存到离线队列');
      return false;
    }
    globalWs.send(JSON.stringify(payload));
    return true;
  }, []);

  const sendCancel = useCallback(() => {
    if (globalWs?.readyState === WebSocket.OPEN) {
      globalWs.send(JSON.stringify({ type: 'cancel' }));
      return true;
    }
    return false;
  }, []);

  const sendCostConfirm = useCallback((confirmed) => {
    if (globalWs?.readyState === WebSocket.OPEN) {
      globalWs.send(JSON.stringify({ type: 'cost_confirmed', confirmed }));
      return true;
    }
    console.warn('WebSocket not connected, cannot send cost confirm');
    return false;
  }, []);

  const onMessage = useCallback((typeOrHandler, handler) => {
    const type = typeof typeOrHandler === 'function' ? '*' : typeOrHandler;
    const fn = typeof typeOrHandler === 'function' ? typeOrHandler : handler;
    if (!globalHandlers.has(type)) {
      globalHandlers.set(type, []);
    }
    globalHandlers.get(type).push(fn);
    return () => {
      const handlers = globalHandlers.get(type) || [];
      const idx = handlers.indexOf(fn);
      if (idx !== -1) handlers.splice(idx, 1);
    };
  }, []);

  return { status, sendMessage, sendRagMessage, sendCrossDocMessage, sendUnifiedChatMessage, sendCostConfirm, sendCancel, onMessage, connect: globalConnect };
}

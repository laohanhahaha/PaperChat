/**
 * WebSocketManager - 封装 WebSocket 连接的核心类
 * 负责：连接/断开、消息收发、重连逻辑、状态管理
 * useWebSocket Hook 作为 React 绑定层使用此类
 */

export type WsStatus = 'disconnected' | 'connecting' | 'connected';
export type MessageHandler = (data: any) => void;

const WS_BASE = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
const DEFAULT_MAX_RETRIES = 5;
const DEFAULT_RETRY_DELAY = 3000;

export class WebSocketManager {
  private ws: WebSocket | null = null;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private handlers: Map<string, MessageHandler[]> = new Map();
  private statusListeners: Set<() => void> = new Set();

  status: WsStatus = 'disconnected';
  retryCount = 0;

  private readonly maxRetries: number;
  private readonly retryDelay: number;

  constructor(maxRetries = DEFAULT_MAX_RETRIES, retryDelay = DEFAULT_RETRY_DELAY) {
    this.maxRetries = maxRetries;
    this.retryDelay = retryDelay;
  }

  // ---------- 连接管理 ----------

  connect(): void {
    if (
      this.ws?.readyState === WebSocket.OPEN ||
      this.ws?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    this._setStatus('connecting');
    const token = localStorage.getItem('token');
    const url = token ? `${WS_BASE}?token=${token}` : WS_BASE;
    const ws = new WebSocket(url);

    ws.onopen = () => {
      this.retryCount = 0;
      this._setStatus('connected');
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);
        const type: string = data.type;
        (this.handlers.get(type) || []).forEach(fn => fn(data));
        (this.handlers.get('*') || []).forEach(fn => fn(data));
      } catch (err) {
        console.error('[WebSocketManager] message parse error:', err);
      }
    };

    ws.onclose = () => {
      this.ws = null;
      this._setStatus('disconnected');
      if (this.retryCount < this.maxRetries) {
        this.retryCount++;
        this.retryTimer = setTimeout(() => this.connect(), this.retryDelay);
      }
    };

    ws.onerror = (err: Event) => {
      console.error('[WebSocketManager] error:', err);
    };

    this.ws = ws;
  }

  disconnect(): void {
    if (this.retryTimer !== null) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this._setStatus('disconnected');
  }

  // ---------- 发送消息 ----------

  send(type: string, payload: Record<string, unknown> = {}): boolean {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type, ...payload }));
      return true;
    }
    console.warn('[WebSocketManager] not connected, cannot send:', type);
    return false;
  }

  sendRaw(data: Record<string, unknown>): boolean {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
      return true;
    }
    console.warn('[WebSocketManager] not connected, cannot send raw message');
    return false;
  }

  // ---------- 消息订阅 ----------

  /**
   * 订阅消息
   * @param typeOrHandler - 消息类型字符串 或 通配符处理函数
   * @param handler - 当 typeOrHandler 为字符串时的处理函数
   * @returns 取消订阅函数
   */
  onMessage(handler: MessageHandler): () => void;
  onMessage(type: string, handler: MessageHandler): () => void;
  onMessage(typeOrHandler: string | MessageHandler, handler?: MessageHandler): () => void {
    const type = typeof typeOrHandler === 'function' ? '*' : typeOrHandler;
    const fn = typeof typeOrHandler === 'function' ? typeOrHandler : handler!;
    if (!this.handlers.has(type)) {
      this.handlers.set(type, []);
    }
    this.handlers.get(type)!.push(fn);
    return () => {
      const list = this.handlers.get(type) || [];
      const idx = list.indexOf(fn);
      if (idx !== -1) list.splice(idx, 1);
    };
  }

  // ---------- 状态订阅（供 useSyncExternalStore 使用） ----------

  subscribeStatus(listener: () => void): () => void {
    this.statusListeners.add(listener);
    return () => this.statusListeners.delete(listener);
  }

  getStatus(): WsStatus {
    return this.status;
  }

  // ---------- 私有方法 ----------

  private _setStatus(newStatus: WsStatus): void {
    this.status = newStatus;
    this.statusListeners.forEach(fn => fn());
  }
}

// 全局单例（与旧版行为保持一致）
export const globalWsManager = new WebSocketManager();

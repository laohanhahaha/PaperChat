/**
 * 离线操作队列
 * 离线时缓冲用户操作，网络恢复后 FIFO 重放
 * 写入 ~1ms/操作
 */
const QUEUE_KEY = 'paperchat_offline_queue';

class OfflineQueue {
  constructor() {
    this._listeners = [];
  }

  /** 获取队列 */
  getQueue() {
    try {
      return JSON.parse(localStorage.getItem(QUEUE_KEY) || '[]');
    } catch {
      return [];
    }
  }

  /** 入队操作 */
  enqueue(operation) {
    const queue = this.getQueue();
    queue.push({
      id: Date.now() + '_' + Math.random().toString(36).substr(2, 9),
      timestamp: Date.now(),
      ...operation,
    });
    localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
    this._notify();
    return queue.length;
  }

  /** 出队（FIFO） */
  dequeue() {
    const queue = this.getQueue();
    if (queue.length === 0) return null;
    const item = queue.shift();
    localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
    this._notify();
    return item;
  }

  /** 清空队列 */
  clear() {
    localStorage.removeItem(QUEUE_KEY);
    this._notify();
  }

  /** 队列长度 */
  get size() {
    return this.getQueue().length;
  }

  /** 重放所有操作 */
  async replayAll(executor) {
    let item;
    const results = [];
    while ((item = this.dequeue()) !== null) {
      try {
        const result = await executor(item);
        results.push({ success: true, item, result });
      } catch (error) {
        results.push({ success: false, item, error: error.message });
        // 失败的重新入队
        this.enqueue(item);
        break; // 停止重放
      }
    }
    return results;
  }

  /** 订阅变更 */
  subscribe(listener) {
    this._listeners.push(listener);
    return () => {
      this._listeners = this._listeners.filter(l => l !== listener);
    };
  }

  _notify() {
    this._listeners.forEach(l => l(this.getQueue()));
  }
}

export const offlineQueue = new OfflineQueue();
export default offlineQueue;

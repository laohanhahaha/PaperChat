import { useRef, useCallback, useEffect } from 'react';

/**
 * 打字机效果 Hook
 * 使用 requestAnimationFrame 替代 setTimeout，与浏览器刷新率同步
 * 
 * @param {Function} updateLastMessage - 更新消息内容的回调
 * @param {Function} onComplete - 打字完成时的回调
 * @param {Object} options - 配置项
 * @param {number} options.charInterval - 字符更新间隔（ms），默认 50
 * @param {number} options.charsPerTick - 每次更新的字符数，默认 3
 */
export function useTypewriter(updateLastMessage, onComplete, options = {}) {
  const { charInterval = 50, charsPerTick = 3 } = options;
  
  const fullContentRef = useRef('');
  const displayedLenRef = useRef(0);
  const isDoneRef = useRef(false);
  const isRunningRef = useRef(false);
  const rafRef = useRef(null);
  const lastTimeRef = useRef(0);
  const tickRef = useRef(null);

  const tick = useCallback((timestamp) => {
    if (!isRunningRef.current) return;
    
    // 节流：确保更新间隔不小于 charInterval
    if (timestamp - lastTimeRef.current < charInterval) {
      rafRef.current = requestAnimationFrame(tickRef.current);
      return;
    }
    lastTimeRef.current = timestamp;

    const full = fullContentRef.current;
    const currentLen = displayedLenRef.current;

    if (currentLen < full.length) {
      const step = Math.min(charsPerTick, full.length - currentLen);
      displayedLenRef.current = currentLen + step;
      updateLastMessage(full.slice(0, displayedLenRef.current));
      rafRef.current = requestAnimationFrame(tickRef.current);
    } else if (isDoneRef.current) {
      // 所有内容已显示且流式完成
      updateLastMessage(full);
      isRunningRef.current = false;
      onComplete?.();
    } else {
      // 内容追上了但流式还没结束，等待新内容
      rafRef.current = null;
    }
  }, [updateLastMessage, onComplete, charInterval, charsPerTick]);

  // tick 变化时更新 ref
  useEffect(() => {
    tickRef.current = tick;
  }, [tick]);

  const appendContent = useCallback((content) => {
    fullContentRef.current += content;
    // 如果当前没有在运行，启动动画
    if (!rafRef.current && isRunningRef.current) {
      rafRef.current = requestAnimationFrame(tickRef.current);
    }
  }, []);

  const start = useCallback(() => {
    isRunningRef.current = true;
    isDoneRef.current = false;
    lastTimeRef.current = 0;
    rafRef.current = requestAnimationFrame(tickRef.current);
  }, []);

  const markDone = useCallback(() => {
    isDoneRef.current = true;
    // 如果当前没有在运行动画，立即启动以完成剩余内容
    if (!rafRef.current) {
      rafRef.current = requestAnimationFrame(tickRef.current);
    }
  }, []);

  const stop = useCallback(() => {
    isRunningRef.current = false;
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    stop();
    fullContentRef.current = '';
    displayedLenRef.current = 0;
    isDoneRef.current = false;
  }, [stop]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, []);

  return {
    appendContent,  // 追加流式内容
    start,          // 开始打字动画
    markDone,       // 标记流式完成
    stop,           // 停止动画
    reset,          // 重置状态
    fullContentRef, // 暴露 ref 供外部读取完整内容
    isRunningRef,   // 暴露运行状态
  };
}

export default useTypewriter;

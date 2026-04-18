import { useState, useEffect, useRef, useCallback } from 'react';
import styles from './ReadingAssist.module.css';

const CHAR_INTERVAL = 30; // 每个字符的显示间隔（毫秒）

// 术语缓存
const termCache = new Map();

/**
 * 阅读辅助面板组件
 * 显示术语解释、摘要、翻译结果
 * 
 * Props:
 * - type: 'explain' | 'summarize' | 'translate'
 * - content: string (输入文本)
 * - term: string (术语，用于 explain 类型)
 * - position: { x, y } (显示位置)
 * - visible: boolean
 * - onClose: () => void
 */
function ReadingAssist({ type, content, term, position, visible, onClose }) {
  const [displayedText, setDisplayedText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isComplete, setIsComplete] = useState(false);
  
  const fullContentRef = useRef('');
  const displayedLenRef = useRef(0);
  const timerRef = useRef(null);
  const abortControllerRef = useRef(null);
  const panelRef = useRef(null);

  // 获取标题
  const getTitle = () => {
    switch (type) {
      case 'explain':
        return '📖 术语解释';
      case 'summarize':
        return '📝 文本摘要';
      case 'translate':
        return '🌐 翻译';
      default:
        return '阅读辅助';
    }
  };

  // 逐字显示的核心函数
  const tickDisplay = useCallback(() => {
    const full = fullContentRef.current;
    const currentLen = displayedLenRef.current;

    if (currentLen < full.length) {
      displayedLenRef.current = currentLen + 1;
      const displayed = full.slice(0, displayedLenRef.current);
      setDisplayedText(displayed);
      timerRef.current = setTimeout(tickDisplay, CHAR_INTERVAL);
    } else {
      // 所有字符已显示
      timerRef.current = null;
      setIsComplete(true);
    }
  }, []);

  // 启动逐字显示
  const startTick = useCallback(() => {
    if (!timerRef.current) {
      timerRef.current = setTimeout(tickDisplay, CHAR_INTERVAL);
    }
  }, [tickDisplay]);

  // 停止逐字显示
  const stopTick = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // 调用后端 API 获取流式结果
  const fetchStreamResult = useCallback(async () => {
    if (!content || !visible) return;

    // 检查缓存（仅对术语解释）
    if (type === 'explain' && term && termCache.has(term)) {
      fullContentRef.current = termCache.get(term);
      displayedLenRef.current = 0;
      setDisplayedText('');
      setIsLoading(false);
      setIsComplete(false);
      startTick();
      return;
    }

    setIsLoading(true);
    setError(null);
    setIsComplete(false);
    setDisplayedText('');
    fullContentRef.current = '';
    displayedLenRef.current = 0;

    // 取消之前的请求
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    try {
      let endpoint;
      let body;

      switch (type) {
        case 'explain':
          endpoint = '/api/v1/reading/explain-term';
          body = { term: term || content, context: content };
          break;
        case 'summarize':
          endpoint = '/api/v1/reading/summarize';
          body = { text: content };
          break;
        case 'translate':
          endpoint = '/api/v1/reading/translate';
          body = { text: content, target_lang: 'zh' };
          break;
        default:
          throw new Error('未知类型');
      }

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify(body),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error('请求失败');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            
            if (data === '[DONE]') {
              // 流结束
              break;
            } else if (data.startsWith('[ERROR]')) {
              setError(data.slice(8));
            } else {
              fullContentRef.current += data;
              startTick();
            }
          }
        }
      }

      // 保存到缓存（仅对术语解释）
      if (type === 'explain' && term) {
        termCache.set(term, fullContentRef.current);
      }

    } catch (err) {
      if (err.name !== 'AbortError') {
        setError(err.message || '请求失败');
      }
    } finally {
      setIsLoading(false);
    }
  }, [type, content, term, visible, startTick]);

  // 组件挂载/更新时获取数据
  useEffect(() => {
    if (visible) {
      fetchStreamResult();
    }

    return () => {
      stopTick();
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [visible, type, content, term, fetchStreamResult, stopTick]);

  // 点击外部关闭
  useEffect(() => {
    if (!visible) return;

    const handleClickOutside = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        onClose?.();
      }
    };

    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
    }, 100);

    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [visible, onClose]);

  // 复制结果
  const handleCopy = () => {
    navigator.clipboard.writeText(fullContentRef.current || displayedText);
  };

  if (!visible) return null;

  // 计算面板位置
  const panelWidth = 360;
  const panelHeight = 280;
  
  let left = position?.x || window.innerWidth / 2;
  let top = (position?.y || window.innerHeight / 2) - panelHeight - 20;

  // 边界检查
  if (left + panelWidth > window.innerWidth - 20) {
    left = window.innerWidth - panelWidth - 20;
  }
  if (left < 20) {
    left = 20;
  }
  if (top < 20) {
    top = (position?.y || window.innerHeight / 2) + 20;
  }

  return (
    <div
      ref={panelRef}
      className={styles.panel}
      style={{
        left: `${left}px`,
        top: `${top}px`,
        width: `${panelWidth}px`,
      }}
    >
      {/* 标题栏 */}
      <div className={styles.header}>
        <span className={styles.title}>{getTitle()}</span>
        <div className={styles.actions}>
          <button
            className={styles.iconBtn}
            onClick={handleCopy}
            title="复制"
            disabled={!displayedText}
          >
            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
              <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
            </svg>
          </button>
          <button
            className={styles.iconBtn}
            onClick={onClose}
            title="关闭"
          >
            <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
            </svg>
          </button>
        </div>
      </div>

      {/* 内容区域 */}
      <div className={styles.content}>
        {isLoading && !displayedText && (
          <div className={styles.loading}>
            <div className={styles.spinner} />
            <span>思考中...</span>
          </div>
        )}

        {error && (
          <div className={styles.error}>
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
            </svg>
            <span>{error}</span>
          </div>
        )}

        {displayedText && (
          <div className={styles.text}>
            {displayedText}
            {!isComplete && <span className={styles.cursor}>|</span>}
          </div>
        )}
      </div>
    </div>
  );
}

export default ReadingAssist;

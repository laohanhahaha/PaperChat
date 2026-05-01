import React from 'react';
import useNetworkStatus from '../../hooks/useNetworkStatus';
import offlineQueue from '../../services/offlineQueue';
import { useState, useEffect, useRef } from 'react';

/**
 * 离线状态横幅 — 顶部黄色提示条
 */
export default function OfflineBanner({ searchSource }) {
  const { isOnline, lastOnlineAt } = useNetworkStatus();
  const [queueSize, setQueueSize] = useState(offlineQueue.size);
  const hideTimerRef = useRef(null);
  const [dismissedAfter, setDismissedAfter] = useState(0);

  useEffect(() => {
    const unsub = offlineQueue.subscribe((queue) => {
      setQueueSize(queue.length);
    });
    return unsub;
  }, []);

  useEffect(() => {
    if (isOnline && lastOnlineAt) {
      // 网络恢复后，3 秒后自动隐藏
      hideTimerRef.current = setTimeout(() => {
        setDismissedAfter(Date.now());
      }, 3000);
    }
    return () => {
      if (hideTimerRef.current) {
        clearTimeout(hideTimerRef.current);
      }
    };
  }, [isOnline, lastOnlineAt]);

  // 离线时始终显示；在线时，如果在恢复后的 3 秒内且未手动隐藏则显示
  const visible = !isOnline || (
    lastOnlineAt &&
    dismissedAfter < lastOnlineAt
  );

  if (!visible) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      zIndex: 9999,
      padding: '8px 16px',
      backgroundColor: isOnline ? '#d4edda' : '#fff3cd',
      color: isOnline ? '#155724' : '#856404',
      textAlign: 'center',
      fontSize: '14px',
      borderBottom: `1px solid ${isOnline ? '#c3e6cb' : '#ffeaa7'}`,
      transition: 'all 0.3s ease',
    }}>
      {isOnline
        ? '网络已恢复，正在同步离线操作...'
        : `当前离线，操作已缓存${queueSize > 0 ? `（${queueSize} 项待同步）` : ''}，联网后自动同步`
      }
      {!isOnline && searchSource === 'offline_cache' && (
        <span style={{ marginLeft: 8, fontWeight: 600 }}>
          · 搜索结果仅限缓存论文
        </span>
      )}
    </div>
  );
}

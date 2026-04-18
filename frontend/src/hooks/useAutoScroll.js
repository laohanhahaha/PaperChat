import { useRef, useEffect } from 'react';

/**
 * 自动滚动 Hook
 * 当依赖项变化时，自动将目标元素滚动到可视区域
 *
 * @param {Array} deps - 触发滚动的依赖数组
 * @returns {React.RefObject} - 需要绑定到滚动目标元素的 ref
 */
export function useAutoScroll(deps) {
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deps is a dynamic array passed by the caller; we intentionally forward it as-is
  }, deps);

  return messagesEndRef;
}

export default useAutoScroll;

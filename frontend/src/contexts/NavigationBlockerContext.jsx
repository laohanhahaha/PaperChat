import { createContext, useContext, useCallback, useRef } from 'react';

const NavigationBlockerContext = createContext(null);

/**
 * 导航拦截 Provider
 * 允许页面注册导航拦截器，在用户尝试离开时收到通知
 */
export function NavigationBlockerProvider({ children }) {
    // 使用 ref 存储拦截回调，避免 Navbar 因拦截状态变化而频繁重渲染
    const blockerRef = useRef(null);

    /**
     * 注册导航拦截器
     * @param {Function|null} onAttempt - 当用户尝试导航时调用的回调，接收目标路径参数
     *   传入 null 清除拦截
     */
    const setBlocker = useCallback((onAttempt) => {
        blockerRef.current = onAttempt;
    }, []);

    /**
     * 尝试导航，如果存在拦截器则触发回调并阻止导航
     * @param {string} targetPath - 目标路径
     * @param {Function} navigateFn - 实际的导航函数
     * @returns {boolean} 是否被拦截
     */
    const tryNavigate = useCallback((targetPath, navigateFn) => {
        if (blockerRef.current) {
            blockerRef.current(targetPath);
            return true; // 被拦截，不导航
        }
        navigateFn(targetPath);
        return false; // 未被拦截，已导航
    }, []);

    return (
        <NavigationBlockerContext.Provider value={{ setBlocker, tryNavigate }}>
            {children}
        </NavigationBlockerContext.Provider>
    );
}

/**
 * 获取导航拦截上下文
 */
export function useNavigationBlockerContext() {
    const ctx = useContext(NavigationBlockerContext);
    if (!ctx) {
        throw new Error('useNavigationBlockerContext must be used within NavigationBlockerProvider');
    }
    return ctx;
}

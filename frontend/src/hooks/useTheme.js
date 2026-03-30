import { useEffect } from 'react';
import useSettingsStore from '../stores/settingsStore';

// 本地存储 key
const THEME_STORAGE_KEY = 'paperchat_theme';
const FONT_SIZE_STORAGE_KEY = 'paperchat_font_size';
const COMPACT_MODE_STORAGE_KEY = 'paperchat_compact_mode';

/**
 * 主题管理 Hook
 * 负责应用主题、字体大小、紧凑模式等外观设置
 */
export default function useTheme() {
    const settings = useSettingsStore(state => state.settings);
    
    // 应用主题
    useEffect(() => {
        const theme = settings?.appearance?.theme?.value || 
                      localStorage.getItem(THEME_STORAGE_KEY) || 
                      'auto';
        
        const root = document.documentElement;
        
        if (theme === 'auto') {
            // 移除 data-theme 属性，让 CSS 媒体查询接管
            root.removeAttribute('data-theme');
        } else {
            // 设置明确的主题
            root.setAttribute('data-theme', theme);
        }
        
        // 保存到 localStorage
        localStorage.setItem(THEME_STORAGE_KEY, theme);
    }, [settings?.appearance?.theme?.value]);
    
    // 应用字体大小
    useEffect(() => {
        const fontSize = settings?.appearance?.font_size?.value || 
                         parseFloat(localStorage.getItem(FONT_SIZE_STORAGE_KEY)) || 
                         1.0;
        
        document.documentElement.style.fontSize = `${fontSize * 16}px`;
        
        // 保存到 localStorage
        localStorage.setItem(FONT_SIZE_STORAGE_KEY, fontSize.toString());
    }, [settings?.appearance?.font_size?.value]);
    
    // 应用紧凑模式
    useEffect(() => {
        const compact = settings?.appearance?.compact_mode?.value;
        const storedCompact = localStorage.getItem(COMPACT_MODE_STORAGE_KEY);
        
        const isCompact = compact !== undefined 
            ? compact 
            : storedCompact === 'true';
        
        if (isCompact) {
            document.documentElement.setAttribute('data-compact', 'true');
        } else {
            document.documentElement.removeAttribute('data-compact');
        }
        
        // 保存到 localStorage
        localStorage.setItem(COMPACT_MODE_STORAGE_KEY, isCompact.toString());
    }, [settings?.appearance?.compact_mode?.value]);
}

/**
 * 初始化主题（在应用启动时调用，避免闪烁）
 * 从 localStorage 读取并立即应用
 */
export function initializeTheme() {
    const root = document.documentElement;
    
    // 主题
    const theme = localStorage.getItem(THEME_STORAGE_KEY) || 'auto';
    if (theme !== 'auto') {
        root.setAttribute('data-theme', theme);
    }
    
    // 字体大小
    const fontSize = parseFloat(localStorage.getItem(FONT_SIZE_STORAGE_KEY)) || 1.0;
    root.style.fontSize = `${fontSize * 16}px`;
    
    // 紧凑模式
    const compact = localStorage.getItem(COMPACT_MODE_STORAGE_KEY) === 'true';
    if (compact) {
        root.setAttribute('data-compact', 'true');
    }
}

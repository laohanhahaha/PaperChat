import { create } from 'zustand';
import api from '../api';

// 本地存储 keys
const THEME_STORAGE_KEY = 'paperchat_theme';
const FONT_SIZE_STORAGE_KEY = 'paperchat_font_size';
const COMPACT_MODE_STORAGE_KEY = 'paperchat_compact_mode';

const useSettingsStore = create((set, get) => ({
    settings: null,        // 完整配置（含元数据）
    loading: false,
    saving: false,
    error: null,
    hasChanges: false,     // 是否有未保存的更改
    pendingChanges: {},    // 待保存的更改
    toastMessage: null,    // 提示消息

    fetchSettings: async () => {
        set({ loading: true, error: null });
        try {
            const res = await api.get('/settings');
            const settings = res.data;
            
            // 同步外观设置到 localStorage（用于快速加载避免闪烁）
            if (settings?.appearance) {
                const theme = settings.appearance.theme?.value;
                const fontSize = settings.appearance.font_size?.value;
                const compactMode = settings.appearance.compact_mode?.value;
                
                if (theme) localStorage.setItem(THEME_STORAGE_KEY, theme);
                if (fontSize) localStorage.setItem(FONT_SIZE_STORAGE_KEY, fontSize.toString());
                if (compactMode !== undefined) localStorage.setItem(COMPACT_MODE_STORAGE_KEY, compactMode.toString());
            }
            
            set({ settings, loading: false, hasChanges: false, pendingChanges: {} });
        } catch (err) {
            set({ error: err.response?.data?.detail || '加载设置失败', loading: false });
        }
    },

    updateLocalSetting: (group, key, value) => {
        // 本地更新（不立即保存）
        set(state => {
            const newSettings = JSON.parse(JSON.stringify(state.settings));
            if (newSettings[group] && newSettings[group][key]) {
                newSettings[group][key].value = value;
            }
            const newPending = { ...state.pendingChanges };
            if (!newPending[group]) newPending[group] = {};
            newPending[group][key] = value;
            
            // 对于外观设置，立即同步到 localStorage
            if (group === 'appearance') {
                if (key === 'theme') localStorage.setItem(THEME_STORAGE_KEY, value);
                if (key === 'font_size') localStorage.setItem(FONT_SIZE_STORAGE_KEY, value.toString());
                if (key === 'compact_mode') localStorage.setItem(COMPACT_MODE_STORAGE_KEY, value.toString());
            }
            
            return { settings: newSettings, hasChanges: true, pendingChanges: newPending };
        });
    },

    saveSettings: async () => {
        const { pendingChanges } = get();
        if (!Object.keys(pendingChanges).length) return;
        set({ saving: true, error: null });
        try {
            const res = await api.put('/settings', pendingChanges);
            const settings = res.data;
            
            // 同步外观设置到 localStorage
            if (settings?.appearance) {
                const theme = settings.appearance.theme?.value;
                const fontSize = settings.appearance.font_size?.value;
                const compactMode = settings.appearance.compact_mode?.value;
                
                if (theme) localStorage.setItem(THEME_STORAGE_KEY, theme);
                if (fontSize) localStorage.setItem(FONT_SIZE_STORAGE_KEY, fontSize.toString());
                if (compactMode !== undefined) localStorage.setItem(COMPACT_MODE_STORAGE_KEY, compactMode.toString());
            }
            
            set({ 
                settings, 
                saving: false, 
                hasChanges: false, 
                pendingChanges: {},
                toastMessage: '设置已保存'
            });
            // 3秒后清除提示
            setTimeout(() => set({ toastMessage: null }), 3000);
        } catch (err) {
            set({ error: err.response?.data?.detail || '保存失败', saving: false });
        }
    },

    resetSettings: async () => {
        if (!window.confirm('确定要重置所有设置为默认值吗？')) return;
        set({ saving: true, error: null });
        try {
            const res = await api.post('/settings/reset');
            const settings = res.data;
            
            // 同步外观设置到 localStorage
            if (settings?.appearance) {
                const theme = settings.appearance.theme?.value;
                const fontSize = settings.appearance.font_size?.value;
                const compactMode = settings.appearance.compact_mode?.value;
                
                if (theme) localStorage.setItem(THEME_STORAGE_KEY, theme);
                if (fontSize) localStorage.setItem(FONT_SIZE_STORAGE_KEY, fontSize.toString());
                if (compactMode !== undefined) localStorage.setItem(COMPACT_MODE_STORAGE_KEY, compactMode.toString());
            }
            
            set({ 
                settings, 
                saving: false, 
                hasChanges: false, 
                pendingChanges: {},
                toastMessage: '设置已重置为默认值'
            });
            setTimeout(() => set({ toastMessage: null }), 3000);
        } catch (err) {
            set({ error: err.response?.data?.detail || '重置失败', saving: false });
        }
    },

    clearToast: () => set({ toastMessage: null })
}));

export default useSettingsStore;

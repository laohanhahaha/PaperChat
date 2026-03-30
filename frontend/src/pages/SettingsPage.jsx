import { useState, useEffect, useCallback } from 'react';
import useSettingsStore from '../stores/settingsStore';
import styles from './SettingsPage.module.css';

// 分组配置
const GROUP_CONFIG = {
    appearance: { title: '个性化设置', icon: '🎨' },
    llm: { title: 'AI 模型设置', icon: '🤖' },
    rag: { title: 'RAG 检索设置', icon: '🔍' },
    search: { title: '联网搜索设置', icon: '🌐' },
    recommendation: { title: '推荐设置', icon: '📊' },
    general: { title: '通用设置', icon: '⚙️' }
};

// 主题选项配置
const THEME_OPTIONS = [
    { value: 'light', icon: '☀️', label: '浅色' },
    { value: 'dark', icon: '🌙', label: '深色' },
    { value: 'auto', icon: '💻', label: '跟随系统' }
];

// 设置控件组件
function SettingControl({ group, settingKey, config, onChange }) {
    const { value, type, label, description, min, max, step, options } = config;
    const [showPassword, setShowPassword] = useState(false);

    switch (type) {
        case 'slider':
            return (
                <div className={styles.settingItem}>
                    <div className={styles.settingHeader}>
                        <label className={styles.settingLabel}>{label}</label>
                        <span className={styles.settingValue}>{value}</span>
                    </div>
                    {description && <p className={styles.settingDesc}>{description}</p>}
                    <input
                        type="range"
                        min={min}
                        max={max}
                        step={step}
                        value={value}
                        onChange={e => onChange(group, settingKey, parseFloat(e.target.value))}
                        className={styles.slider}
                    />
                    <div className={styles.sliderRange}>
                        <span>{min}</span>
                        <span>{max}</span>
                    </div>
                </div>
            );

        case 'number':
            return (
                <div className={styles.settingItem}>
                    <div className={styles.settingHeader}>
                        <label className={styles.settingLabel}>{label}</label>
                    </div>
                    {description && <p className={styles.settingDesc}>{description}</p>}
                    <div className={styles.numberInputWrapper}>
                        <input
                            type="number"
                            min={min}
                            max={max}
                            value={value}
                            onChange={e => {
                                const val = parseFloat(e.target.value);
                                if (!isNaN(val)) {
                                    onChange(group, settingKey, Math.max(min, Math.min(max, val)));
                                }
                            }}
                            className={styles.numberInput}
                        />
                        <span className={styles.inputRange}>范围: {min} - {max}</span>
                    </div>
                </div>
            );

        case 'select':
            return (
                <div className={styles.settingItem}>
                    <div className={styles.settingHeader}>
                        <label className={styles.settingLabel}>{label}</label>
                    </div>
                    {description && <p className={styles.settingDesc}>{description}</p>}
                    <select
                        value={value}
                        onChange={e => onChange(group, settingKey, e.target.value)}
                        className={styles.selectInput}
                    >
                        {options.map(opt => (
                            <option key={opt} value={opt}>{opt}</option>
                        ))}
                    </select>
                </div>
            );

        case 'text':
            return (
                <div className={styles.settingItem}>
                    <div className={styles.settingHeader}>
                        <label className={styles.settingLabel}>{label}</label>
                    </div>
                    {description && <p className={styles.settingDesc}>{description}</p>}
                    <input
                        type="text"
                        value={value || ''}
                        onChange={e => onChange(group, settingKey, e.target.value)}
                        className={styles.textInput}
                        placeholder={`请输入${label}`}
                    />
                </div>
            );

        case 'password':
            return (
                <div className={styles.settingItem}>
                    <div className={styles.settingHeader}>
                        <label className={styles.settingLabel}>{label}</label>
                    </div>
                    {description && <p className={styles.settingDesc}>{description}</p>}
                    <div className={styles.passwordWrapper}>
                        <input
                            type={showPassword ? 'text' : 'password'}
                            value={value || ''}
                            onChange={e => onChange(group, settingKey, e.target.value)}
                            className={styles.passwordInput}
                            placeholder="留空则使用默认 Key"
                        />
                        <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className={styles.passwordToggle}
                            title={showPassword ? '隐藏' : '显示'}
                        >
                            {showPassword ? '🙈' : '👁️'}
                        </button>
                    </div>
                </div>
            );

        case 'toggle':
            return (
                <div className={styles.settingItem}>
                    <div className={styles.toggleWrapper}>
                        <div>
                            <label className={styles.settingLabel}>{label}</label>
                            {description && <p className={styles.settingDesc}>{description}</p>}
                        </div>
                        <button
                            type="button"
                            className={`${styles.toggleSwitch} ${value ? styles.active : ''}`}
                            onClick={() => onChange(group, settingKey, !value)}
                            aria-pressed={value}
                            aria-label={label}
                        />
                    </div>
                </div>
            );

        case 'theme':
            return (
                <div className={styles.settingItem}>
                    <div className={styles.settingHeader}>
                        <label className={styles.settingLabel}>{label}</label>
                    </div>
                    {description && <p className={styles.settingDesc}>{description}</p>}
                    <div className={styles.themeSelector}>
                        {THEME_OPTIONS.map(opt => (
                            <div
                                key={opt.value}
                                className={`${styles.themeOption} ${value === opt.value ? styles.active : ''}`}
                                onClick={() => onChange(group, settingKey, opt.value)}
                            >
                                <span className={styles.themeOptionIcon}>{opt.icon}</span>
                                <span className={styles.themeOptionLabel}>{opt.label}</span>
                            </div>
                        ))}
                    </div>
                </div>
            );

        default:
            return null;
    }
}

// 设置分组卡片
function SettingSection({ groupKey, title, icon, settings, onChange }) {
    const settingEntries = Object.entries(settings);

    return (
        <div className={styles.sectionCard}>
            <div className={styles.sectionHeader}>
                <span className={styles.sectionIcon}>{icon}</span>
                <h3 className={styles.sectionTitle}>{title}</h3>
            </div>
            <div className={styles.sectionContent}>
                {settingEntries.map(([key, config]) => (
                    <SettingControl
                        key={key}
                        group={groupKey}
                        settingKey={key}
                        config={config}
                        onChange={onChange}
                    />
                ))}
            </div>
        </div>
    );
}

export default function SettingsPage() {
    const {
        settings,
        loading,
        saving,
        error,
        hasChanges,
        toastMessage,
        fetchSettings,
        updateLocalSetting,
        saveSettings,
        resetSettings
    } = useSettingsStore();

    // 加载设置
    useEffect(() => {
        fetchSettings();
    }, [fetchSettings]);

    // 处理设置变更
    const handleChange = useCallback((group, key, value) => {
        updateLocalSetting(group, key, value);
    }, [updateLocalSetting]);

    // 保存设置
    const handleSave = useCallback(() => {
        saveSettings();
    }, [saveSettings]);

    // 重置设置
    const handleReset = useCallback(() => {
        resetSettings();
    }, [resetSettings]);

    // 加载中
    if (loading) {
        return (
            <div className={styles.container}>
                <div className={styles.loading}>
                    <div className={styles.spinner}></div>
                    <p>加载设置中...</p>
                </div>
            </div>
        );
    }

    // 错误状态
    if (error && !settings) {
        return (
            <div className={styles.container}>
                <div className={styles.error}>
                    <p>⚠️ {error}</p>
                    <button onClick={() => fetchSettings()}>重试</button>
                </div>
            </div>
        );
    }

    return (
        <div className={styles.container}>
            {/* 头部 */}
            <header className={styles.header}>
                <h1 className={styles.title}>⚙️ 系统设置</h1>
                <p className={styles.subtitle}>配置 AI 模型、检索参数和系统行为</p>
            </header>

            {/* 设置分组 */}
            <div className={styles.sections}>
                {settings && Object.entries(settings).map(([groupKey, groupSettings]) => {
                    const config = GROUP_CONFIG[groupKey];
                    if (!config) return null;
                    return (
                        <SettingSection
                            key={groupKey}
                            groupKey={groupKey}
                            title={config.title}
                            icon={config.icon}
                            settings={groupSettings}
                            onChange={handleChange}
                        />
                    );
                })}
            </div>

            {/* 底部操作栏 */}
            <div className={styles.actionBar}>
                <button
                    onClick={handleReset}
                    className={styles.resetBtn}
                    disabled={saving}
                >
                    🔄 重置为默认
                </button>
                <button
                    onClick={handleSave}
                    className={`${styles.saveBtn} ${hasChanges ? styles.saveBtnActive : ''}`}
                    disabled={!hasChanges || saving}
                >
                    {saving ? '保存中...' : '💾 保存设置'}
                </button>
            </div>

            {/* 提示消息 */}
            {toastMessage && (
                <div className={styles.toast}>
                    {toastMessage}
                </div>
            )}

            {/* 错误提示 */}
            {error && (
                <div className={styles.errorToast}>
                    ⚠️ {error}
                </div>
            )}
        </div>
    );
}

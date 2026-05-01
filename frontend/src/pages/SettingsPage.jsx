import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import useSettingsStore from '../stores/settingsStore';
import { useNavigationBlockerContext } from '../contexts/NavigationBlockerContext';
import ConfigAgentPanel from '../components/Config/ConfigAgentPanel';
import ModelManager from '../components/Settings/ModelManager';
import SubAgentManager from '../components/SubAgentManager/SubAgentManager';
import styles from './SettingsPage.module.css';

// 分组配置
const GROUP_CONFIG = {
    appearance: { title: '个性化设置', icon: '🎨' },
    llm: { title: 'AI 模型设置', icon: '🤖' },
    routing: { title: '智能路由', icon: '🧭' },
    rag: { title: 'RAG 检索设置', icon: '🔍' },
    search: { title: '联网搜索设置', icon: '🌐' },
    mcp: { title: 'MCP 学术服务', icon: '🔌' },
    subagents: { title: '子智能体管理', icon: '🤖' },
    recommendation: { title: '推荐设置', icon: '📊' },
    precache: { title: '预缓存设置', icon: '📦' },
    general: { title: '通用设置', icon: '⚙️' }
};

// 主题选项配置
const THEME_OPTIONS = [
    { value: 'light', icon: '☀️', label: '浅色' },
    { value: 'dark', icon: '🌙', label: '深色' },
    { value: 'auto', icon: '💻', label: '跟随系统' }
];

// Select 选项中文标签映射
const OPTION_LABELS = {
    model_mode: {
        smart_route: '智能路由',
        local_only: '本地优先',
        cloud_only: '云端优先'
    }
};

// 设置控件组件
function SettingControl({ group, settingKey, config, onChange }) {
    let { value, type, label, description, min, max, step, options } = config;
    const [showPassword, setShowPassword] = useState(false);

    // routing 分组特殊渲染处理
    if (group === 'routing') {
        if (settingKey === 'budget_limit') {
            description = description
                ? `${description}（0 表示无限制）`
                : '0 表示无限制';
        }
        if (settingKey === 'confirm_threshold') {
            type = 'number';
            description = '超过此金额将弹窗确认';
        }
    }

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
                        {options.map(opt => {
                            const optLabel = OPTION_LABELS[settingKey]?.[opt] || opt;
                            return <option key={opt} value={opt}>{optLabel}</option>;
                        })}
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

        case 'multi_select': {
            const selectedValues = Array.isArray(value) ? value : [];
            return (
                <div className={styles.settingItem}>
                    <div className={styles.settingHeader}>
                        <label className={styles.settingLabel}>{label}</label>
                    </div>
                    {description && <p className={styles.settingDesc}>{description}</p>}
                    <div className={styles.checkboxGroup}>
                        {options.map(opt => {
                            const optValue = typeof opt === 'object' ? opt.value : opt;
                            const optLabel = typeof opt === 'object' ? opt.label : opt;
                            const isChecked = selectedValues.includes(optValue);
                            return (
                                <label key={optValue} className={styles.checkboxLabel}>
                                    <input
                                        type="checkbox"
                                        checked={isChecked}
                                        onChange={e => {
                                            const newValues = e.target.checked
                                                ? [...selectedValues, optValue]
                                                : selectedValues.filter(v => v !== optValue);
                                            onChange(group, settingKey, newValues);
                                        }}
                                        className={styles.checkboxInput}
                                    />
                                    <span className={styles.checkboxText}>{optLabel}</span>
                                </label>
                            );
                        })}
                    </div>
                </div>
            );
        }

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

// 未保存更改确认弹窗
function UnsavedChangesDialog({ onSaveAndLeave, onDiscard, onContinueEditing, saving }) {
    return (
        <div className={styles.dialogOverlay} onClick={onContinueEditing}>
            <div className={styles.dialogCard} onClick={e => e.stopPropagation()}>
                <div className={styles.dialogHeader}>
                    <span className={styles.dialogIcon}>⚠️</span>
                    <h3 className={styles.dialogTitle}>未保存的更改</h3>
                </div>
                <p className={styles.dialogMessage}>
                    您有未保存的设置更改，是否保存？
                </p>
                <div className={styles.dialogActions}>
                    <button
                        className={styles.dialogBtnContinue}
                        onClick={onContinueEditing}
                        disabled={saving}
                    >
                        继续编辑
                    </button>
                    <button
                        className={styles.dialogBtnDiscard}
                        onClick={onDiscard}
                        disabled={saving}
                    >
                        放弃更改
                    </button>
                    <button
                        className={styles.dialogBtnSave}
                        onClick={onSaveAndLeave}
                        disabled={saving}
                    >
                        {saving ? '保存中...' : '保存并离开'}
                    </button>
                </div>
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

    const navigate = useNavigate();
    const { setBlocker } = useNavigationBlockerContext();

    // 未保存更改弹窗状态
    const [showDialog, setShowDialog] = useState(false);
    const [pendingPath, setPendingPath] = useState(null);

    // 用于在保存完成后导航的 ref（避免闭包问题）
    const pendingPathRef = useRef(null);

    // 加载设置
    useEffect(() => {
        fetchSettings();
    }, [fetchSettings]);

    // 注册/清除导航拦截器
    useEffect(() => {
        if (hasChanges) {
            setBlocker((targetPath) => {
                setPendingPath(targetPath);
                pendingPathRef.current = targetPath;
                setShowDialog(true);
            });
        } else {
            setBlocker(null);
        }

        return () => setBlocker(null);
    }, [hasChanges, setBlocker]);

    // beforeunload 事件：拦截浏览器关闭/刷新
    useEffect(() => {
        if (!hasChanges) return;

        const handleBeforeUnload = (event) => {
            event.preventDefault();
            // 现代浏览器需要设置 returnValue
            event.returnValue = '';
            return '';
        };

        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, [hasChanges]);

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

    // 弹窗操作：保存并离开
    const handleSaveAndLeave = useCallback(async () => {
        try {
            await saveSettings();
            // saveSettings 成功后 hasChanges 变为 false，上面的 useEffect 会自动导航
            // 但为了保险，也在这里手动导航
            const target = pendingPathRef.current || pendingPath;
            if (target) {
                setBlocker(null);
                navigate(target);
            }
            setShowDialog(false);
            pendingPathRef.current = null;
            setPendingPath(null);
        } catch {
            // 保存失败，留在当前页面，弹窗保持打开
        }
    }, [saveSettings, navigate, pendingPath, setBlocker]);

    // 弹窗操作：放弃更改
    const handleDiscard = useCallback(async () => {
        // 重新从服务器获取设置，丢弃所有本地修改
        await fetchSettings();
        setBlocker(null);
        const target = pendingPathRef.current || pendingPath;
        if (target) {
            navigate(target);
        }
        setShowDialog(false);
        pendingPathRef.current = null;
        setPendingPath(null);
    }, [fetchSettings, navigate, pendingPath, setBlocker]);

    // 弹窗操作：继续编辑
    const handleContinueEditing = useCallback(() => {
        setShowDialog(false);
        pendingPathRef.current = null;
        setPendingPath(null);
    }, []);

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
                    // MCP 服务分组使用 ConfigAgentPanel 组件
                    if (groupKey === 'mcp') {
                        return (
                            <div key={groupKey} className={styles.sectionCard}>
                                <div className={styles.sectionHeader}>
                                    <span className={styles.sectionIcon}>{config.icon}</span>
                                    <h3 className={styles.sectionTitle}>{config.title}</h3>
                                </div>
                                <div className={styles.sectionContent}>
                                    <ConfigAgentPanel />
                                </div>
                            </div>
                        );
                    }

                    // 子智能体已在循环外独立渲染，跳过
                    if (groupKey === 'subagents') return null;

                    // LLM 分组：顶部显示 ModelManager，下方保留 temperature / max_tokens 等控件
                    if (groupKey === 'llm') {
                        // 从 llm 分组中提取需要保留的设置项（排除 model_name / api_key / api_base_url）
                        const LLM_EXCLUDE_KEYS = ['model_name', 'api_key', 'api_base_url'];
                        const remainingSettings = Object.fromEntries(
                            Object.entries(groupSettings).filter(([k]) => !LLM_EXCLUDE_KEYS.includes(k))
                        );
                        return (
                            <div key={groupKey} className={styles.sectionCard}>
                                <div className={styles.sectionHeader}>
                                    <span className={styles.sectionIcon}>{config.icon}</span>
                                    <h3 className={styles.sectionTitle}>{config.title}</h3>
                                </div>
                                <div className={styles.sectionContent}>
                                    <ModelManager />
                                    {Object.keys(remainingSettings).length > 0 && (
                                        <div style={{ marginTop: '16px', borderTop: '1px solid var(--color-border)', paddingTop: '16px' }}>
                                            {Object.entries(remainingSettings).map(([key, cfg]) => (
                                                <SettingControl
                                                    key={key}
                                                    group={groupKey}
                                                    settingKey={key}
                                                    config={cfg}
                                                    onChange={handleChange}
                                                />
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    }
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
                })
            }

                {/* 子智能体管理（独立渲染，不依赖后端 settings 字段） */}
                <div className={styles.sectionCard}>
                    <div className={styles.sectionHeader}>
                        <span className={styles.sectionIcon}>🤖</span>
                        <h3 className={styles.sectionTitle}>子智能体管理</h3>
                    </div>
                    <div className={styles.sectionContent}>
                        <SubAgentManager />
                    </div>
                </div>
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

            {/* 未保存更改确认弹窗 */}
            {showDialog && (
                <UnsavedChangesDialog
                    onSaveAndLeave={handleSaveAndLeave}
                    onDiscard={handleDiscard}
                    onContinueEditing={handleContinueEditing}
                    saving={saving}
                />
            )}
        </div>
    );
}

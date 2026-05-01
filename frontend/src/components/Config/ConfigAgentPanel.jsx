import { useState, useEffect, useCallback } from 'react';
import configApi from '../../api/configApi';
import styles from './ConfigAgentPanel.module.css';

// 服务图标映射
const SERVICE_ICONS = {
  academic_mcp: '🎓',
  open_websearch: '🔍',
  zotero: '📚',
};

// 服务状态映射
const STATUS_MAP = {
  healthy: { label: '已连接', className: styles.healthy },
  unhealthy: { label: '异常', className: styles.unhealthy },
  not_configured: { label: '未配置', className: styles.not_configured },
  unknown: { label: '未知', className: styles.unknown },
};

export default function ConfigAgentPanel() {
  const [statuses, setStatuses] = useState({});
  const [expandedService, setExpandedService] = useState(null);
  const [apiKeyInputs, setApiKeyInputs] = useState({});
  const [settingsInputs, setSettingsInputs] = useState({});
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(null);
  const [message, setMessage] = useState(null);

  // 加载服务状态
  const fetchStatus = useCallback(async () => {
    try {
      const res = await configApi.getServiceStatus();
      setStatuses(res.data.statuses || {});
    } catch (err) {
      console.error('获取服务状态失败:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // 一键配置免费服务
  const handleAutoSetup = async () => {
    setActionLoading('auto-setup');
    setMessage(null);
    try {
      const res = await configApi.autoSetup();
      const { configured, failed } = res.data;
      if (failed.length === 0) {
        setMessage({ type: 'success', text: `成功配置 ${configured.length} 个免费服务：${configured.join(', ')}` });
      } else {
        setMessage({
          type: 'error',
          text: `已配置: ${configured.join(', ')}；失败: ${failed.join(', ')}`,
        });
      }
      await fetchStatus();
    } catch (err) {
      setMessage({ type: 'error', text: '一键配置失败: ' + (err.response?.data?.detail || err.message) });
    } finally {
      setActionLoading(null);
    }
  };

  // 配置单个服务
  const handleConfigure = async (serviceName) => {
    setActionLoading(serviceName);
    setMessage(null);
    try {
      const config = {
        api_key: apiKeyInputs[serviceName] || '',
        settings: settingsInputs[serviceName] || {},
      };
      const res = await configApi.configureService(serviceName, config);
      setMessage({ type: 'success', text: res.data.message });
      setExpandedService(null);
      setApiKeyInputs((prev) => {
        const next = { ...prev };
        delete next[serviceName];
        return next;
      });
      await fetchStatus();
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || '配置失败' });
    } finally {
      setActionLoading(null);
    }
  };

  // 验证服务
  const handleValidate = async (serviceName) => {
    setActionLoading(`validate-${serviceName}`);
    setMessage(null);
    try {
      const res = await configApi.validateService(serviceName);
      const { valid, message: msg } = res.data;
      setMessage({
        type: valid ? 'success' : 'error',
        text: msg,
      });
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || '验证失败' });
    } finally {
      setActionLoading(null);
    }
  };

  // 所有服务定义（从状态推断 + 硬编码补充）
  const allServices = [
    { name: 'academic_mcp', display_name: 'Academic MCP', requires_api_key: false, optional_api_key: false, description: '学术论文搜索、下载与阅读，覆盖 18 个平台' },
    { name: 'open_websearch', display_name: 'Open WebSearch', requires_api_key: false, optional_api_key: false, description: '通用网络搜索，支持 9 个搜索引擎' },
    { name: 'zotero', display_name: 'Zotero', requires_api_key: true, optional_api_key: false, description: '个人文献管理' },
  ];

  if (loading) {
    return (
      <div className={styles.loading}>
        <div className={styles.spinner} />
        <span>加载服务状态...</span>
      </div>
    );
  }

  return (
    <div>
      {/* 工具栏 */}
      <div className={styles.toolbar}>
        <span className={styles.toolbarTitle}>
          学术服务管理
        </span>
        <div className={styles.toolbarActions}>
          <button
            className={styles.btnPrimary}
            onClick={handleAutoSetup}
            disabled={actionLoading === 'auto-setup'}
          >
            {actionLoading === 'auto-setup' ? '配置中...' : '🚀 一键配置免费服务'}
          </button>
          <button
            className={styles.btn}
            onClick={fetchStatus}
            disabled={!!actionLoading}
          >
            🔄 刷新
          </button>
        </div>
      </div>

      {/* 消息提示 */}
      {message && (
        <div className={`${styles.statusMessage} ${styles[message.type]}`}>
          {message.text}
        </div>
      )}

      {/* 服务卡片网格 */}
      <div className={styles.serviceGrid}>
        {allServices.map((svc) => {
          const status = statuses[svc.name]?.status || 'not_configured';
          const statusInfo = STATUS_MAP[status] || STATUS_MAP.not_configured;
          const isExpanded = expandedService === svc.name;
          const icon = SERVICE_ICONS[svc.name] || '⚙️';

          return (
            <div
              key={svc.name}
              className={`${styles.serviceCard} ${isExpanded ? styles.expanded : ''}`}
              onClick={() => !isExpanded && setExpandedService(svc.name)}
            >
              <div className={styles.cardHeader}>
                <div className={styles.serviceIcon}>{icon}</div>
                <div className={styles.serviceInfo}>
                  <p className={styles.serviceName}>
                    {svc.display_name}
                    {svc.requires_api_key && <span className={`${styles.tag} ${styles.tagKey}`}>需 Key</span>}
                    {!svc.requires_api_key && !svc.optional_api_key && <span className={`${styles.tag} ${styles.tagFree}`}>免费</span>}
                    {svc.optional_api_key && <span className={`${styles.tag} ${styles.tagOptional}`}>可选 Key</span>}
                  </p>
                  <p className={styles.serviceDesc}>{svc.description}</p>
                </div>
                <div className={`${styles.statusDot} ${statusInfo.className}`} title={statusInfo.label} />
              </div>

              {/* 展开详情 */}
              {isExpanded && (
                <div className={styles.cardDetail} onClick={(e) => e.stopPropagation()}>
                  {/* API Key 输入 */}
                  {(svc.requires_api_key || svc.optional_api_key) && (
                    <div className={styles.inputGroup}>
                      <label className={styles.inputLabel}>API Key</label>
                      <input
                        type="password"
                        className={styles.textInput}
                        placeholder={svc.requires_api_key ? '请输入 API Key' : '可选，提升限额'}
                        value={apiKeyInputs[svc.name] || ''}
                        onChange={(e) =>
                          setApiKeyInputs((prev) => ({ ...prev, [svc.name]: e.target.value }))
                        }
                      />
                    </div>
                  )}

                  {/* Zotero 特殊字段 */}
                  {svc.name === 'zotero' && (
                    <div className={styles.inputGroup}>
                      <label className={styles.inputLabel}>Library ID</label>
                      <input
                        type="text"
                        className={styles.textInput}
                        placeholder="你的 Zotero 用户 ID"
                        value={settingsInputs[svc.name]?.library_id || ''}
                        onChange={(e) =>
                          setSettingsInputs((prev) => ({
                            ...prev,
                            [svc.name]: { ...prev[svc.name], library_id: e.target.value },
                          }))
                        }
                      />
                    </div>
                  )}

                  {/* 操作按钮 */}
                  <div className={styles.actionButtons}>
                    <button
                      className={styles.btnPrimary}
                      onClick={() => handleConfigure(svc.name)}
                      disabled={actionLoading === svc.name}
                    >
                      {actionLoading === svc.name ? '配置中...' : '配置并启动'}
                    </button>
                    {status !== 'not_configured' && (
                      <button
                        className={styles.btn}
                        onClick={() => handleValidate(svc.name)}
                        disabled={actionLoading === `validate-${svc.name}`}
                      >
                        {actionLoading === `validate-${svc.name}` ? '验证中...' : '验证'}
                      </button>
                    )}
                    <button
                      className={styles.btn}
                      onClick={() => {
                        setExpandedService(null);
                        setApiKeyInputs((prev) => {
                          const next = { ...prev };
                          delete next[svc.name];
                          return next;
                        });
                      }}
                    >
                      收起
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* AI 配置助手入口 */}
      <div className={styles.aiHelper}>
        <p className={styles.aiHelperTitle}>🤖 AI 配置助手</p>
        <p className={styles.aiHelperDesc}>在对话框中输入配置需求，AI 助手将自动帮你完成配置</p>
        <p className={styles.aiHelperDesc}>
          试试说："帮我配置学术搜索服务" 或 "查看所有服务状态"
        </p>
      </div>
    </div>
  );
}

import { useState, useCallback } from 'react';
import configApi from '../../api/configApi';
import styles from './SetupWizard.module.css';

// 免费服务列表
const FREE_SERVICES = [
  { name: 'arxiv', display: 'arXiv', icon: '📄', desc: '预印本论文搜索，无需 API Key' },
  { name: 'semantic_scholar', display: 'Semantic Scholar', icon: '🎓', desc: '学术论文搜索与引用分析，可选 API Key' },
  { name: 'crossref', display: 'CrossRef', icon: '🔗', desc: 'DOI 解析与学术元数据，无需 API Key' },
  { name: 'dblp', display: 'DBLP', icon: '💻', desc: '计算机科学文献数据库，无需 API Key' },
];

// 付费/需要 API Key 的服务
const PAID_SERVICES = [
  { name: 'zotero', display: 'Zotero', icon: '📚', desc: '个人文献管理', keyLabel: 'Zotero API Key', extraFields: [{ key: 'library_id', label: 'Library ID', placeholder: '输入 Zotero 用户 ID' }] },
  { name: 'bing', display: 'Bing 搜索', icon: '🔍', desc: '通用网络搜索', keyLabel: 'Bing Search API Key' },
  { name: 'tavily', display: 'Tavily 搜索', icon: '🤖', desc: 'AI 优化搜索', keyLabel: 'Tavily API Key' },
  { name: 'brave', display: 'Brave 搜索', icon: '🦁', desc: '隐私优先搜索', keyLabel: 'Brave Search API Key' },
];

const STEPS = ['welcome', 'free', 'paid', 'done'];

export default function SetupWizard({ onComplete }) {
  const [step, setStep] = useState(0);
  const [configuring, setConfiguring] = useState(false);
  const [configuredFree, setConfiguredFree] = useState([]);
  const [failedFree, setFailedFree] = useState([]);
  const [paidKeys, setPaidKeys] = useState({});
  const [paidExtra, setPaidExtra] = useState({});
  const [paidResults, setPaidResults] = useState({});
  const [configuringPaid, setConfiguringPaid] = useState(null);

  const currentStep = STEPS[step];

  // 一键配置免费服务
  const handleAutoSetup = useCallback(async () => {
    setConfiguring(true);
    try {
      const res = await configApi.autoSetup();
      setConfiguredFree(res.data.configured || []);
      setFailedFree(res.data.failed || []);
    } catch (err) {
      console.error('一键配置失败:', err);
      setFailedFree(FREE_SERVICES.map(s => s.name));
    } finally {
      setConfiguring(false);
    }
  }, []);

  // 单个免费服务配置
  const handleConfigureFree = useCallback(async (serviceName) => {
    setConfiguring(true);
    try {
      await configApi.configureService(serviceName, {});
      setConfiguredFree(prev => [...new Set([...prev, serviceName])]);
    } catch (err) {
      console.error(`配置 ${serviceName} 失败:`, err);
      setFailedFree(prev => [...new Set([...prev, serviceName])]);
    } finally {
      setConfiguring(false);
    }
  }, []);

  // 配置付费服务
  const handleConfigurePaid = useCallback(async (service) => {
    const apiKey = paidKeys[service.name] || '';
    if (!apiKey.trim()) return;

    setConfiguringPaid(service.name);
    try {
      const settings = {};
      // 处理额外字段（如 Zotero library_id）
      if (service.extraFields) {
        for (const field of service.extraFields) {
          const val = paidExtra[`${service.name}_${field.key}`];
          if (val) settings[field.key] = val;
        }
      }
      await configApi.configureService(service.name, {
        api_key: apiKey.trim(),
        settings: Object.keys(settings).length > 0 ? settings : undefined,
      });
      setPaidResults(prev => ({ ...prev, [service.name]: 'success' }));
    } catch (err) {
      console.error(`配置 ${service.name} 失败:`, err);
      setPaidResults(prev => ({ ...prev, [service.name]: 'failed' }));
    } finally {
      setConfiguringPaid(null);
    }
  }, [paidKeys, paidExtra]);

  // 完成向导
  const handleComplete = useCallback(() => {
    localStorage.setItem('setup_completed', 'true');
    onComplete?.();
  }, [onComplete]);

  // 跳过向导
  const handleSkip = useCallback(() => {
    localStorage.setItem('setup_completed', 'true');
    onComplete?.();
  }, [onComplete]);

  const goNext = () => setStep(prev => Math.min(prev + 1, STEPS.length - 1));
  const goBack = () => setStep(prev => Math.max(prev - 1, 0));

  return (
    <div className={styles.overlay}>
      <div className={styles.wizard}>
        {/* 进度条 */}
        <div className={styles.progressBar}>
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`${styles.progressDot} ${i <= step ? styles.active : ''} ${i === step ? styles.current : ''}`}
            />
          ))}
        </div>

        {/* 步骤1: 欢迎页 */}
        {currentStep === 'welcome' && (
          <div className={styles.step}>
            <div className={styles.welcomeIcon}>🎓</div>
            <h1 className={styles.title}>欢迎使用 PaperChat</h1>
            <p className={styles.subtitle}>
              你的 AI 学术研究助手，帮你搜索论文、管理引用、追踪研究前沿
            </p>
            <div className={styles.features}>
              <div className={styles.feature}>
                <span className={styles.featureIcon}>📄</span>
                <span>论文搜索与阅读</span>
              </div>
              <div className={styles.feature}>
                <span className={styles.featureIcon}>🔗</span>
                <span>引用管理与格式化</span>
              </div>
              <div className={styles.feature}>
                <span className={styles.featureIcon}>💡</span>
                <span>智能问答与分析</span>
              </div>
              <div className={styles.feature}>
                <span className={styles.featureIcon}>📚</span>
                <span>文献管理与同步</span>
              </div>
            </div>
            <p className={styles.hint}>
              接下来我们将为你配置学术服务，让 PaperChat 发挥全部能力
            </p>
            <div className={styles.actions}>
              <button className={styles.primaryBtn} onClick={goNext}>
                开始配置
              </button>
              <button className={styles.skipBtn} onClick={handleSkip}>
                以后再配
              </button>
            </div>
          </div>
        )}

        {/* 步骤2: 免费服务 */}
        {currentStep === 'free' && (
          <div className={styles.step}>
            <h2 className={styles.stepTitle}>免费学术服务</h2>
            <p className={styles.stepDesc}>
              这些服务无需 API Key，可一键启用，让你的学术搜索更强大
            </p>
            <div className={styles.serviceGrid}>
              {FREE_SERVICES.map(svc => {
                const isConfigured = configuredFree.includes(svc.name);
                const isFailed = failedFree.includes(svc.name);
                return (
                  <div key={svc.name} className={`${styles.serviceCard} ${isConfigured ? styles.configured : ''} ${isFailed ? styles.failed : ''}`}>
                    <div className={styles.serviceIcon}>{svc.icon}</div>
                    <div className={styles.serviceInfo}>
                      <div className={styles.serviceName}>{svc.display}</div>
                      <div className={styles.serviceDesc}>{svc.desc}</div>
                    </div>
                    {isConfigured ? (
                      <span className={styles.badgeSuccess}>已配置</span>
                    ) : isFailed ? (
                      <button
                        className={styles.retryBtn}
                        onClick={() => handleConfigureFree(svc.name)}
                        disabled={configuring}
                      >
                        重试
                      </button>
                    ) : (
                      <button
                        className={styles.configureBtn}
                        onClick={() => handleConfigureFree(svc.name)}
                        disabled={configuring}
                      >
                        启用
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
            <div className={styles.actions}>
              <button className={styles.secondaryBtn} onClick={handleAutoSetup} disabled={configuring}>
                {configuring ? '配置中...' : '一键全部启用'}
              </button>
              <div className={styles.navBtns}>
                <button className={styles.ghostBtn} onClick={goBack}>上一步</button>
                <button className={styles.primaryBtn} onClick={goNext}>下一步</button>
              </div>
            </div>
          </div>
        )}

        {/* 步骤3: 付费服务 */}
        {currentStep === 'paid' && (
          <div className={styles.step}>
            <h2 className={styles.stepTitle}>高级服务（可选）</h2>
            <p className={styles.stepDesc}>
              以下服务需要 API Key，配置后可获得更丰富的搜索与文献管理能力。你可以跳过此步骤
            </p>
            <div className={styles.paidList}>
              {PAID_SERVICES.map(svc => {
                const result = paidResults[svc.name];
                const isConfiguring = configuringPaid === svc.name;
                return (
                  <div key={svc.name} className={styles.paidCard}>
                    <div className={styles.paidHeader}>
                      <span className={styles.serviceIcon}>{svc.icon}</span>
                      <div>
                        <div className={styles.serviceName}>{svc.display}</div>
                        <div className={styles.serviceDesc}>{svc.desc}</div>
                      </div>
                    </div>
                    {result === 'success' ? (
                      <span className={styles.badgeSuccess}>已配置</span>
                    ) : (
                      <div className={styles.paidFields}>
                        <input
                          type="password"
                          className={styles.input}
                          placeholder={svc.keyLabel}
                          value={paidKeys[svc.name] || ''}
                          onChange={e => setPaidKeys(prev => ({ ...prev, [svc.name]: e.target.value }))}
                        />
                        {svc.extraFields?.map(field => (
                          <input
                            key={field.key}
                            type="text"
                            className={styles.input}
                            placeholder={field.placeholder}
                            value={paidExtra[`${svc.name}_${field.key}`] || ''}
                            onChange={e => setPaidExtra(prev => ({ ...prev, [`${svc.name}_${field.key}`]: e.target.value }))}
                          />
                        ))}
                        <button
                          className={styles.configureBtn}
                          onClick={() => handleConfigurePaid(svc)}
                          disabled={isConfiguring || !(paidKeys[svc.name] || '').trim()}
                        >
                          {isConfiguring ? '配置中...' : '配置'}
                        </button>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <div className={styles.actions}>
              <button className={styles.ghostBtn} onClick={goBack}>上一步</button>
              <button className={styles.primaryBtn} onClick={goNext}>下一步</button>
            </div>
          </div>
        )}

        {/* 步骤4: 完成 */}
        {currentStep === 'done' && (
          <div className={styles.step}>
            <div className={styles.doneIcon}>✅</div>
            <h2 className={styles.stepTitle}>配置完成！</h2>
            <div className={styles.summary}>
              <div className={styles.summaryItem}>
                <span className={styles.summaryLabel}>免费服务</span>
                <span className={styles.summaryValue}>
                  {configuredFree.length > 0 ? configuredFree.map(n => FREE_SERVICES.find(s => s.name === n)?.display || n).join('、') : '未配置'}
                </span>
              </div>
              <div className={styles.summaryItem}>
                <span className={styles.summaryLabel}>高级服务</span>
                <span className={styles.summaryValue}>
                  {Object.entries(paidResults).filter(([, v]) => v === 'success').map(([k]) => PAID_SERVICES.find(s => s.name === k)?.display || k).join('、') || '未配置'}
                </span>
              </div>
            </div>
            <p className={styles.hint}>
              你随时可以在设置页面修改服务配置
            </p>
            <div className={styles.actions}>
              <button className={styles.ghostBtn} onClick={goBack}>返回修改</button>
              <button className={styles.primaryBtn} onClick={handleComplete}>
                开始使用 PaperChat
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

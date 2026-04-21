import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { getProfile, getRecommendations, updateBlindspot } from '../api/profileApi';
import useAuthStore from '../stores/authStore';
import styles from './ResearchProfilePage.module.css';

/* ===== 常量配置 ===== */
const STAGE_CONFIG = {
  survey: { label: '调研', description: '文献综述与背景研究', color: '#3B82F6' },
  design: { label: '设计', description: '方法设计与模型架构', color: '#10B981' },
  experiment: { label: '实验', description: '实验验证与结果分析', color: '#F59E0B' },
  writing: { label: '写作', description: '论文撰写与投稿准备', color: '#8B5CF6' },
};

const STAGE_ORDER = ['survey', 'design', 'experiment', 'writing'];

const BLINDSPOT_STATUS_CONFIG = {
  blind: { label: '盲区', color: '#EF4444', bgColor: '#FEE2E2' },
  improving: { label: '提升中', color: '#F59E0B', bgColor: '#FEF3C7' },
  mastered: { label: '已掌握', color: '#10B981', bgColor: '#D1FAE5' },
};

const PREFERENCE_CONFIG = {
  methodology: { label: '方法论', color: '#3B82F6' },
  experiment: { label: '实验', color: '#10B981' },
  survey: { label: '综述', color: '#F59E0B' },
  review: { label: '评论', color: '#8B5CF6' },
};

/* ===== 研究领域标签云组件 ===== */
function DomainTagCloud({ domains }) {
  if (!domains || domains.length === 0) {
    return <div className={styles.emptyText}>暂无研究领域数据</div>;
  }

  const getTagStyle = (type) => {
    switch (type) {
      case 'primary':
        return { fontSize: '1.2rem', color: '#3B82F6', fontWeight: 600 };
      case 'sub':
        return { fontSize: '1rem', color: '#10B981', fontWeight: 500 };
      default:
        return { fontSize: '0.85rem', color: '#6B7280', fontWeight: 400 };
    }
  };

  return (
    <div className={styles.tagCloud}>
      {domains.map((domain, index) => (
        <span
          key={index}
          className={styles.domainTag}
          style={getTagStyle(domain.type)}
          title={`频次: ${domain.frequency}`}
        >
          {domain.name}
        </span>
      ))}
    </div>
  );
}

/* ===== 阅读偏好组件 ===== */
function ReadingPreferenceChart({ preferences }) {
  if (!preferences || preferences.length === 0) {
    return <div className={styles.emptyText}>暂无阅读偏好数据</div>;
  }

  const maxCount = Math.max(...preferences.map(p => p.count));

  return (
    <div className={styles.preferenceChart}>
      {preferences.map((pref, index) => {
        const config = PREFERENCE_CONFIG[pref.type] || { label: pref.type, color: '#6B7280' };
        const percentage = maxCount > 0 ? (pref.count / maxCount) * 100 : 0;
        
        return (
          <div key={index} className={styles.preferenceItem}>
            <span className={styles.preferenceLabel}>{config.label}</span>
            <div className={styles.preferenceBar}>
              <div
                className={styles.preferenceFill}
                style={{
                  width: `${percentage}%`,
                  backgroundColor: config.color,
                }}
              />
            </div>
            <span className={styles.preferenceCount}>{pref.count}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ===== 知识盲区列表组件 ===== */
function BlindspotList({ blindspots, onStatusChange }) {
  const handleMarkMastered = async (blindspot) => {
    if (blindspot.status === 'mastered') return;
    await onStatusChange(blindspot.id, 'mastered');
  };

  if (!blindspots || blindspots.length === 0) {
    return <div className={styles.emptyText}>暂无知识盲区数据</div>;
  }

  return (
    <div className={styles.blindspotList}>
      {blindspots.map((blindspot, index) => {
        const statusConfig = BLINDSPOT_STATUS_CONFIG[blindspot.status] || BLINDSPOT_STATUS_CONFIG.blind;
        
        return (
          <div key={index} className={styles.blindspotItem}>
            <div className={styles.blindspotInfo}>
              <span className={styles.blindspotConcept}>{blindspot.concept}</span>
              <span
                className={styles.blindspotBadge}
                style={{
                  backgroundColor: statusConfig.bgColor,
                  color: statusConfig.color,
                }}
              >
                {statusConfig.label}
              </span>
            </div>
            <div className={styles.blindspotMeta}>
              <span className={styles.queryCount}>查询 {blindspot.count} 次</span>
              {blindspot.status !== 'mastered' && (
                <button
                  className={styles.markMasteredBtn}
                  onClick={() => handleMarkMastered(blindspot)}
                >
                  标记为已掌握
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ===== 研究阶段指示器组件 ===== */
function ResearchStageIndicator({ stage, confidence }) {
  if (!stage) {
    return <div className={styles.emptyText}>暂无研究阶段数据</div>;
  }

  const currentIndex = STAGE_ORDER.indexOf(stage.stage);
  const confidencePercent = Math.round((confidence || stage.confidence || 0.5) * 100);

  return (
    <div className={styles.stageIndicator}>
      <div className={styles.stageSteps}>
        {STAGE_ORDER.map((stageKey, index) => {
          const config = STAGE_CONFIG[stageKey];
          const isActive = index <= currentIndex;
          const isCurrent = index === currentIndex;

          return (
            <div key={stageKey} className={styles.stageStep}>
              <div
                className={`${styles.stageDot} ${isActive ? styles.active : ''} ${isCurrent ? styles.current : ''}`}
                style={{
                  backgroundColor: isActive ? config.color : '#E5E7EB',
                  borderColor: isCurrent ? config.color : 'transparent',
                }}
              />
              <span
                className={`${styles.stageLabel} ${isActive ? styles.active : ''} ${isCurrent ? styles.current : ''}`}
                style={{ color: isCurrent ? config.color : undefined }}
              >
                {config.label}
              </span>
              {index < STAGE_ORDER.length - 1 && (
                <div
                  className={`${styles.stageLine} ${index < currentIndex ? styles.active : ''}`}
                />
              )}
            </div>
          );
        })}
      </div>
      <div className={styles.stageConfidence}>
        当前阶段置信度: <strong>{confidencePercent}%</strong>
      </div>
    </div>
  );
}

/* ===== 推荐论文卡片组件 ===== */
function RecommendationCard({ recommendation, onClick }) {
  const sourceConfig = {
    blindspot: { label: '盲区补充', color: '#EF4444', bgColor: '#FEE2E2' },
    domain: { label: '领域相关', color: '#3B82F6', bgColor: '#DBEAFE' },
  };

  const source = sourceConfig[recommendation.source] || sourceConfig.domain;

  return (
    <div className={styles.recommendationCard} onClick={onClick}>
      <div className={styles.recommendationHeader}>
        <span
          className={styles.sourceTag}
          style={{
            backgroundColor: source.bgColor,
            color: source.color,
          }}
        >
          {source.label}
        </span>
      </div>
      <h4 className={styles.recommendationTitle}>{recommendation.title}</h4>
      <p className={styles.recommendationReason}>{recommendation.reason}</p>
    </div>
  );
}

/* ===== 主页面组件 ===== */
export default function ResearchProfilePage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  
  const [profile, setProfile] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // 加载画像数据
  const loadProfile = useCallback(async () => {
    if (!user?.id) return;
    
    try {
      setLoading(true);
      setError(null);
      
      const [profileRes, recRes] = await Promise.all([
        getProfile(user.id),
        getRecommendations(user.id),
      ]);
      
      setProfile(profileRes.data);
      setRecommendations(recRes.data?.recommendations || []);
    } catch (err) {
      console.error('加载研究画像失败:', err);
      setError('加载研究画像失败，请重试');
    } finally {
      setLoading(false);
    }
  }, [user?.id]);

  // 更新盲区状态
  const handleBlindspotStatusChange = useCallback(async (blindspotId, newStatus) => {
    if (!user?.id) return;
    
    try {
      await updateBlindspot(user.id, blindspotId, newStatus);
      // 刷新画像数据
      await loadProfile();
    } catch (err) {
      console.error('更新盲区状态失败:', err);
    }
  }, [user?.id, loadProfile]);

  // 跳转到论文阅读页
  const handleRecommendationClick = useCallback((recommendation) => {
    if (recommendation.paper_id) {
      navigate(`/reader/${recommendation.paper_id}`);
    }
  }, [navigate]);

  // 初始加载
  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>
          <div className={styles.spinner}></div>
          <p>加载研究画像...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={styles.container}>
        <div className={styles.error}>
          <p>{error}</p>
          <button onClick={loadProfile}>重试</button>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* 页面标题 */}
      <header className={styles.header}>
        <h1 className={styles.title}>研究画像</h1>
        <span className={styles.subtitle}>基于您的阅读行为生成的个性化研究分析</span>
      </header>

      {/* 两栏布局 */}
      <div className={styles.content}>
        {/* 左栏：画像信息 */}
        <div className={styles.leftColumn}>
          {/* 研究领域标签云 */}
          <section className={styles.card}>
            <h2 className={styles.cardTitle}>
              <span className={styles.cardIcon}>🏷️</span>
              研究领域
            </h2>
            <DomainTagCloud domains={profile?.domains} />
          </section>

          {/* 阅读偏好 */}
          <section className={styles.card}>
            <h2 className={styles.cardTitle}>
              <span className={styles.cardIcon}>📊</span>
              阅读偏好
            </h2>
            <ReadingPreferenceChart preferences={profile?.preferences} />
          </section>

          {/* 知识盲区 */}
          <section className={styles.card}>
            <h2 className={styles.cardTitle}>
              <span className={styles.cardIcon}>🎯</span>
              知识盲区
            </h2>
            <BlindspotList
              blindspots={profile?.blindspots}
              onStatusChange={handleBlindspotStatusChange}
            />
          </section>

          {/* 研究阶段 */}
          <section className={styles.card}>
            <h2 className={styles.cardTitle}>
              <span className={styles.cardIcon}>🚀</span>
              研究阶段
            </h2>
            <ResearchStageIndicator
              stage={profile?.stage}
              confidence={profile?.stage?.confidence}
            />
          </section>
        </div>

        {/* 右栏：推荐论文 */}
        <div className={styles.rightColumn}>
          <section className={styles.card}>
            <h2 className={styles.cardTitle}>
              <span className={styles.cardIcon}>📚</span>
              推荐论文
            </h2>
            {recommendations.length === 0 ? (
              <div className={styles.emptyRecommendations}>
                <p>暂无推荐论文</p>
                <span className={styles.emptyHint}>多阅读论文以获取个性化推荐</span>
              </div>
            ) : (
              <div className={styles.recommendationList}>
                {recommendations.map((rec, index) => (
                  <RecommendationCard
                    key={index}
                    recommendation={rec}
                    onClick={() => handleRecommendationClick(rec)}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

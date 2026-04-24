import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import recommendationApi from '../../api/recommendationApi';
import styles from './RecommendationPanel.module.css';

/**
 * 综合推荐面板
 * 展示融合内容相似 + 个性化 + 知识图谱的推荐结果，支持有用/无用反馈。
 *
 * @param {Object}  props
 * @param {number}  [props.paperId]        - 当前论文 ID（传入则启用内容相似推荐）
 * @param {number}  [props.topK=8]         - 推荐数量
 * @param {boolean} [props.collapsed]      - 初始是否折叠
 * @param {string}  [props.title]          - 面板标题
 */
function RecommendationPanel({
  paperId,
  topK = 8,
  collapsed: initCollapsed = false,
  title = '综合推荐',
}) {
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(initCollapsed);
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState([]);
  const [feedbackMap, setFeedbackMap] = useState({}); // { [paperId]: 'useful' | 'not_useful' }
  const [feedbackLoading, setFeedbackLoading] = useState({}); // { [paperId]: boolean }

  const fetchRecommendations = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await recommendationApi.getComprehensive({
        paper_id: paperId,
        top_k: topK,
      });
      setItems(resp.data?.recommendations || []);
    } catch (err) {
      console.error('获取综合推荐失败:', err);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [paperId, topK]);

  useEffect(() => {
    fetchRecommendations();
  }, [fetchRecommendations]);

  const handleFeedback = useCallback(async (pid, feedbackType) => {
    if (feedbackMap[pid]) return; // 已反馈，不重复提交
    setFeedbackLoading(prev => ({ ...prev, [pid]: true }));
    try {
      await recommendationApi.submitFeedback({
        paper_id: pid,
        feedback_type: feedbackType,
        source: 'comprehensive',
      });
      setFeedbackMap(prev => ({ ...prev, [pid]: feedbackType }));
    } catch (err) {
      console.error('提交反馈失败:', err);
    } finally {
      setFeedbackLoading(prev => ({ ...prev, [pid]: false }));
    }
  }, [feedbackMap]);

  const handleCardClick = useCallback((pid) => {
    navigate(`/reader/${pid}`);
  }, [navigate]);

  return (
    <div className={styles.panel}>
      {/* 面板头部 */}
      <div className={styles.header}>
        <span className={styles.title}>{title}</span>
        <div className={styles.headerActions}>
          <button
            className={styles.refreshBtn}
            onClick={fetchRecommendations}
            disabled={loading}
            title="刷新推荐"
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
          <button
            className={styles.collapseBtn}
            onClick={() => setCollapsed(c => !c)}
            title={collapsed ? '展开' : '折叠'}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              style={{ transform: collapsed ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      </div>

      {/* 面板主体 */}
      {!collapsed && (
        <div className={styles.body}>
          {loading ? (
            <div className={styles.loadingState}>
              <div className={styles.spinner} />
              <span>正在计算推荐...</span>
            </div>
          ) : items.length === 0 ? (
            <div className={styles.emptyState}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className={styles.emptyIcon}>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              <p>暂无推荐内容，上传更多论文后可获得智能推荐</p>
            </div>
          ) : (
            <ul className={styles.list}>
              {items.map(item => (
                <RecommendationCard
                  key={item.id}
                  item={item}
                  feedback={feedbackMap[item.id]}
                  feedbackLoading={feedbackLoading[item.id]}
                  onClick={handleCardClick}
                  onFeedback={handleFeedback}
                />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

/** 单张推荐卡片 */
function RecommendationCard({ item, feedback, feedbackLoading, onClick, onFeedback }) {
  const hasFeedback = Boolean(feedback);
  const sim = item.similarity;
  const simColor = sim == null ? null
    : sim >= 80 ? '#10b981'
    : sim >= 60 ? '#3b82f6'
    : '#f59e0b';

  return (
    <li className={styles.card} onClick={() => onClick(item.id)}>
      {/* 卡片头：相似度 + 理由 */}
      <div className={styles.cardMeta}>
        {sim != null && (
          <span className={styles.simBadge} style={{ background: `${simColor}18`, color: simColor }}>
            {Math.round(sim)}% 匹配
          </span>
        )}
        {(item.reason || item.match_reason) && (
          <span className={styles.reasonBadge}>
            {item.reason || item.match_reason}
          </span>
        )}
      </div>

      {/* 标题 */}
      <h4 className={styles.cardTitle} title={item.title}>{item.title}</h4>

      {/* 作者 */}
      {item.authors && (
        <p className={styles.cardAuthors} title={item.authors}>{item.authors}</p>
      )}

      {/* 摘要预览 */}
      {item.abstract_preview && (
        <p className={styles.cardAbstract}>{item.abstract_preview}</p>
      )}

      {/* 卡片底部：元信息 + 反馈按钮 */}
      <div className={styles.cardFooter} onClick={e => e.stopPropagation()}>
        <span className={styles.cardInfo}>
          {item.page_count > 0 && `${item.page_count} 页`}
          {item.category && ` · ${item.category}`}
        </span>

        <div className={styles.feedbackBtns}>
          {hasFeedback ? (
            <span className={`${styles.feedbackDone} ${feedback === 'useful' ? styles.useful : styles.notUseful}`}>
              {feedback === 'useful' ? '👍 有用' : '👎 无用'}
            </span>
          ) : (
            <>
              <button
                className={`${styles.feedbackBtn} ${styles.usefulBtn}`}
                onClick={() => onFeedback(item.id, 'useful')}
                disabled={feedbackLoading}
                title="这个推荐有用"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905a3.61 3.61 0 01-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                </svg>
              </button>
              <button
                className={`${styles.feedbackBtn} ${styles.notUsefulBtn}`}
                onClick={() => onFeedback(item.id, 'not_useful')}
                disabled={feedbackLoading}
                title="这个推荐没用"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018c.163 0 .326.02.484.06L17 4m-7 10v2a2 2 0 002 2h.095c.5 0 .905-.405.905-.905a3.61 3.61 0 01.608-2.006L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
                </svg>
              </button>
            </>
          )}
        </div>
      </div>
    </li>
  );
}

export default RecommendationPanel;

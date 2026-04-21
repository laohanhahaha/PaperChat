import { useState, useEffect, useCallback, useRef, memo } from 'react';
import { metricsApi } from '../api/metricsApi';
import styles from './MetricsDashboardPage.module.css';

/* ===== 常量 ===== */
const REFRESH_INTERVAL = 30; // 自动刷新间隔（秒）
const PAGE_SIZE = 20; // 每页运行记录数

/* ===== 骨架屏组件 ===== */
const SkeletonDashboard = memo(() => (
  <div className={styles.container}>
    <header className={styles.header}>
      <div className={styles.headerLeft}>
        <div className={styles.skeletonLine} style={{ width: 200, height: 28 }} />
        <div className={styles.skeletonLine} style={{ width: 280, height: 14 }} />
      </div>
    </header>
    <div className={styles.content}>
      <div className={styles.skeletonRow}>
        {[1, 2, 3, 4].map(i => (
          <div key={i} className={styles.skeletonCard}>
            <div className={`${styles.skeletonLine} ${styles.w60}`} />
            <div className={styles.skeletonBig} />
          </div>
        ))}
      </div>
      <div className={styles.skeletonRow}>
        <div className={styles.skeletonCard} style={{ flex: '0 0 60%' }}>
          <div className={`${styles.skeletonLine} ${styles.w40}`} />
          {[1, 2, 3, 4, 5].map(i => (
            <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'center', marginBottom: 14 }}>
              <div className={styles.skeletonLine} style={{ width: 80, flexShrink: 0 }} />
              <div className={styles.skeletonLine} style={{ flex: 1, height: 20 }} />
              <div className={styles.skeletonLine} style={{ width: 40, flexShrink: 0 }} />
            </div>
          ))}
        </div>
        <div className={styles.skeletonCard} style={{ flex: '0 0 40%' }}>
          <div className={`${styles.skeletonLine} ${styles.w40}`} />
          {[1, 2, 3, 4].map(i => (
            <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <div className={styles.skeletonLine} style={{ flex: 2 }} />
              <div className={styles.skeletonLine} style={{ flex: 1 }} />
              <div className={styles.skeletonLine} style={{ flex: 1 }} />
            </div>
          ))}
        </div>
      </div>
    </div>
  </div>
));

/* ===== 统计卡片组件 ===== */
const StatCard = memo(({ label, value, unit, rateClass }) => (
  <div className={styles.statCard}>
    <span className={styles.statLabel}>{label}</span>
    <div className={`${styles.statValue} ${rateClass || ''}`}>
      {value}
      {unit && <span className={styles.statUnit}>{unit}</span>}
    </div>
  </div>
));

/* ===== 工具排行榜横向柱状图组件 ===== */
const ToolRankingChart = memo(({ tools }) => {
  if (!tools || tools.length === 0) {
    return <div className={styles.emptyText}>暂无工具使用数据</div>;
  }

  const maxCount = Math.max(...tools.map(t => t.count));
  const displayTools = tools.slice(0, 10);

  return (
    <div className={styles.barChart}>
      {displayTools.map((tool) => {
        const pct = maxCount > 0 ? (tool.count / maxCount) * 100 : 0;
        return (
          <div key={tool.tool_name} className={styles.barItem}>
            <span className={styles.barLabel} title={tool.tool_name}>{tool.tool_name}</span>
            <div className={styles.barTrack}>
              <div className={styles.barFill} style={{ width: `${pct}%` }} />
            </div>
            <span className={styles.barCount}>{tool.count}</span>
          </div>
        );
      })}
    </div>
  );
});

/* ===== 工具详细统计表格组件 ===== */
const ToolStatsTable = memo(({ tools }) => {
  if (!tools || tools.length === 0) {
    return <div className={styles.emptyText}>暂无工具统计数据</div>;
  }

  return (
    <div className={styles.toolTableWrapper}>
      <table className={styles.toolTable}>
        <thead>
          <tr>
            <th>工具名</th>
            <th>调用次数</th>
            <th>成功率</th>
            <th>平均耗时</th>
            <th>缓存命中</th>
          </tr>
        </thead>
        <tbody>
          {tools.map((tool) => (
            <tr key={tool.tool_name}>
              <td className={styles.toolName} title={tool.tool_name}>{tool.tool_name}</td>
              <td>{tool.total_calls}</td>
              <td>{(tool.success_rate * 100).toFixed(1)}%</td>
              <td>{tool.avg_duration_ms.toFixed(1)}ms</td>
              <td>{(tool.cache_hit_rate * 100).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
});

/* ===== 最近运行记录组件 ===== */
const RunsTable = memo(({ runs, total, page, onPageChange }) => {
  const totalPages = Math.ceil(total / PAGE_SIZE);

  if (!runs || runs.length === 0) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyIcon}>📋</div>
        <p className={styles.emptyText}>暂无 Agent 运行记录</p>
        <span className={styles.emptyHint}>当 Agent 执行任务后，运行记录将显示在此处</span>
      </div>
    );
  }

  const formatTime = (isoStr) => {
    try {
      const d = new Date(isoStr);
      return d.toLocaleString('zh-CN', {
        month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      });
    } catch {
      return isoStr;
    }
  };

  return (
    <>
      <div className={styles.runsTableWrapper}>
        <table className={styles.runsTable}>
          <thead>
            <tr>
              <th>时间</th>
              <th>模式</th>
              <th>步骤数</th>
              <th>耗时</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.id} className={!run.success ? styles.runFailed : undefined}>
                <td>{formatTime(run.created_at)}</td>
                <td>{run.agent_mode}</td>
                <td>{run.total_steps}</td>
                <td>{run.total_duration_ms.toFixed(1)}ms</td>
                <td>
                  {run.success ? (
                    <span className={`${styles.badge} ${styles.badgeSuccess}`}>成功</span>
                  ) : (
                    <span className={`${styles.badge} ${styles.badgeFail}`} title={run.error_message}>
                      失败
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className={styles.pagination}>
          <button
            className={styles.pageBtn}
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            上一页
          </button>
          <span className={styles.pageInfo}>
            第 {page} / {totalPages} 页（共 {total} 条）
          </span>
          <button
            className={styles.pageBtn}
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
          >
            下一页
          </button>
        </div>
      )}
    </>
  );
});

/* ===== 主页面组件 ===== */
function MetricsDashboardPage() {
  const [dashboard, setDashboard] = useState(null);
  const [runs, setRuns] = useState([]);
  const [runsTotal, setRunsTotal] = useState(0);
  const [toolStats, setToolStats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [countdown, setCountdown] = useState(REFRESH_INTERVAL);
  const refreshTimerRef = useRef(null);
  const countdownRef = useRef(null);

  // 加载数据
  const loadData = useCallback(async (isRefresh = false) => {
    try {
      if (!isRefresh) setLoading(true);
      setError(null);

      const offset = (page - 1) * PAGE_SIZE;
      const [dashRes, runsRes, toolsRes] = await Promise.all([
        metricsApi.getDashboard(),
        metricsApi.getRuns(PAGE_SIZE, offset),
        metricsApi.getToolStats(),
      ]);

      setDashboard(dashRes.data);
      setRuns(runsRes.data?.runs || []);
      setRunsTotal(runsRes.data?.total || 0);
      setToolStats(toolsRes.data?.tools || []);
    } catch (err) {
      console.error('加载监控数据失败:', err);
      if (!isRefresh) setError('加载监控数据失败，请重试');
    } finally {
      setLoading(false);
    }
  }, [page]);

  // 初始加载 + 页码变化时重新加载
  useEffect(() => {
    loadData();
  }, [loadData]);

  // 自动刷新倒计时
  useEffect(() => {
    setCountdown(REFRESH_INTERVAL);

    countdownRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          return REFRESH_INTERVAL;
        }
        return prev - 1;
      });
    }, 1000);

    refreshTimerRef.current = setInterval(() => {
      loadData(true);
    }, REFRESH_INTERVAL * 1000);

    return () => {
      clearInterval(countdownRef.current);
      clearInterval(refreshTimerRef.current);
    };
  }, [page]); // eslint-disable-line react-hooks/exhaustive-deps

  // 页码变化时重置倒计时
  const handlePageChange = useCallback((newPage) => {
    setPage(newPage);
    setCountdown(REFRESH_INTERVAL);
  }, []);

  // 成功率颜色编码
  const getSuccessRateClass = useCallback((rate) => {
    if (rate > 0.9) return styles.rateGreen;
    if (rate > 0.7) return styles.rateYellow;
    return styles.rateRed;
  }, []);

  // 加载中 - 骨架屏
  if (loading && !dashboard) {
    return <SkeletonDashboard />;
  }

  // 错误状态
  if (error && !dashboard) {
    return (
      <div className={styles.container}>
        <div className={styles.error}>
          <p>{error}</p>
          <button onClick={() => loadData()}>重试</button>
        </div>
      </div>
    );
  }

  const successRate = dashboard?.success_rate ?? 0;
  const cacheRate = dashboard?.cache_hit_rate ?? 0;

  return (
    <div className={styles.container}>
      {/* 页面标题 */}
      <header className={styles.header}>
        <div className={styles.headerLeft}>
          <h1 className={styles.title}>Agent 监控仪表盘</h1>
          <span className={styles.subtitle}>实时监控 Agent 运行状态与工具使用情况</span>
        </div>
        <div className={styles.refreshIndicator}>
          <span className={styles.refreshDot} />
          <span>{countdown}s 后刷新</span>
        </div>
      </header>

      <div className={styles.content}>
        {/* 第一行：4 个统计卡片 */}
        <div className={styles.statsRow}>
          <StatCard
            label="总运行次数"
            value={dashboard?.total_runs ?? 0}
          />
          <StatCard
            label="成功率"
            value={`${((successRate) * 100).toFixed(1)}`}
            unit="%"
            rateClass={getSuccessRateClass(successRate)}
          />
          <StatCard
            label="平均延迟"
            value={(dashboard?.avg_duration_ms ?? 0).toFixed(1)}
            unit="ms"
          />
          <StatCard
            label="缓存命中率"
            value={`${(cacheRate * 100).toFixed(1)}`}
            unit="%"
          />
        </div>

        {/* 第二行：工具排行榜 + 工具详细统计 */}
        <div className={styles.middleRow}>
          <div className={styles.chartColumn}>
            <section className={styles.card}>
              <h2 className={styles.cardTitle}>
                <span className={styles.cardIcon}>📊</span>
                工具使用排行榜
              </h2>
              <ToolRankingChart tools={dashboard?.tool_usage_ranking} />
            </section>
          </div>
          <div className={styles.tableColumn}>
            <section className={styles.card}>
              <h2 className={styles.cardTitle}>
                <span className={styles.cardIcon}>🔧</span>
                工具详细统计
              </h2>
              <ToolStatsTable tools={toolStats} />
            </section>
          </div>
        </div>

        {/* 第三行：最近运行记录 */}
        <section className={styles.runsSection}>
          <h2 className={styles.cardTitle}>
            <span className={styles.cardIcon}>📋</span>
            最近运行记录
          </h2>
          <RunsTable
            runs={runs}
            total={runsTotal}
            page={page}
            onPageChange={handlePageChange}
          />
        </section>
      </div>
    </div>
  );
}

export default memo(MetricsDashboardPage);

import { useState, useEffect, useCallback } from 'react';
import subagentApi from '../../api/subagentApi';
import styles from './SubAgentManager.module.css';

// 可选工具列表
const AVAILABLE_TOOLS = [
  { value: 'search_papers', label: '论文检索' },
  { value: 'analyze_paper', label: '论文分析' },
  { value: 'web_search', label: '联网搜索' },
  { value: 'knowledge_graph', label: '知识图谱' },
  { value: 'citation_analysis', label: '引用分析' },
  { value: 'summarize', label: '文本摘要' },
  { value: 'translate', label: '翻译' },
  { value: 'recommend', label: '推荐' },
];

// 根据名称匹配图标（与 AgentProgress 保持一致）
function getAgentIcon(name) {
  if (!name) return '🤖';
  const n = name.toLowerCase();
  if (n.includes('检索') || n.includes('search') || n.includes('retriev')) return '🔍';
  if (n.includes('分析') || n.includes('analyz') || n.includes('evaluat')) return '📊';
  if (n.includes('推荐') || n.includes('recommend') || n.includes('suggest')) return '💡';
  if (n.includes('综述') || n.includes('review') || n.includes('survey')) return '📝';
  if (n.includes('对比') || n.includes('compar')) return '⚖️';
  if (n.includes('写作') || n.includes('writ')) return '✍️';
  if (n.includes('翻译') || n.includes('translat')) return '🌐';
  if (n.includes('数据') || n.includes('data') || n.includes('统计')) return '📈';
  if (n.includes('方法') || n.includes('method')) return '🧪';
  return '🤖';
}

// 空表单
const EMPTY_FORM = { name: '', description: '', system_prompt: '', tools: [] };

export default function SubAgentManager() {
  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);

  // 表单弹窗状态
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  // 删除确认弹窗
  const [deleteTarget, setDeleteTarget] = useState(null);

  // 加载列表
  const fetchAgents = useCallback(async () => {
    try {
      setLoading(true);
      const res = await subagentApi.list();
      setAgents(Array.isArray(res.data) ? res.data : (res.data?.items || []));
    } catch {
      // 错误由 axios 拦截器统一处理
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  // 打开新建
  const handleAdd = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setShowForm(true);
  };

  // 打开编辑
  const handleEdit = (agent) => {
    setEditingId(agent.id);
    setForm({
      name: agent.name || '',
      description: agent.description || '',
      system_prompt: agent.system_prompt || '',
      tools: agent.tools || [],
    });
    setShowForm(true);
  };

  // 提交表单
  const handleSubmit = async () => {
    if (!form.name.trim()) return;
    setSubmitting(true);
    try {
      if (editingId) {
        await subagentApi.update(editingId, form);
      } else {
        await subagentApi.create(form);
      }
      setShowForm(false);
      setEditingId(null);
      setForm(EMPTY_FORM);
      fetchAgents();
    } catch {
      // 错误由拦截器处理
    } finally {
      setSubmitting(false);
    }
  };

  // 删除
  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await subagentApi.delete(deleteTarget.id);
      setDeleteTarget(null);
      fetchAgents();
    } catch {
      // 错误由拦截器处理
    }
  };

  // 工具多选切换
  const toggleTool = (tool) => {
    setForm(prev => ({
      ...prev,
      tools: prev.tools.includes(tool)
        ? prev.tools.filter(t => t !== tool)
        : [...prev.tools, tool],
    }));
  };

  if (loading) {
    return <div className={styles.loading}>加载子智能体列表...</div>;
  }

  return (
    <div className={styles.container}>
      {/* 顶部操作栏 */}
      <div className={styles.toolbar}>
        <span className={styles.toolbarTitle}>
          共 {agents.length} 个智能体
        </span>
        <button className={styles.addBtn} onClick={handleAdd}>
          ＋ 新建智能体
        </button>
      </div>

      {/* 卡片列表 */}
      {agents.length === 0 ? (
        <div className={styles.empty}>
          <div className={styles.emptyIcon}>🤖</div>
          暂无子智能体，点击上方按钮新建
        </div>
      ) : (
        <div className={styles.grid}>
          {agents.map(agent => (
            <div
              key={agent.id}
              className={`${styles.card} ${agent.is_preset ? styles.cardPreset : ''}`}
            >
              <div className={styles.cardHeader}>
                <span className={styles.cardIcon}>{getAgentIcon(agent.name)}</span>
                <span className={styles.cardName}>{agent.name}</span>
                {agent.is_preset && (
                  <span className={styles.presetBadge}>🔒 系统预置</span>
                )}
              </div>
              {agent.description && (
                <div className={styles.cardDesc}>{agent.description}</div>
              )}
              {agent.tools && agent.tools.length > 0 && (
                <div className={styles.cardTools}>
                  {agent.tools.map(t => (
                    <span key={t} className={styles.toolTag}>{t}</span>
                  ))}
                </div>
              )}
              {!agent.is_preset && (
                <div className={styles.cardActions}>
                  <button className={styles.editBtn} onClick={() => handleEdit(agent)}>
                    编辑
                  </button>
                  <button className={styles.deleteBtn} onClick={() => setDeleteTarget(agent)}>
                    删除
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 新建/编辑弹窗 */}
      {showForm && (
        <div className={styles.overlay} onClick={() => setShowForm(false)}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>
            <h3 className={styles.modalTitle}>
              {editingId ? '编辑智能体' : '新建智能体'}
            </h3>

            <div className={styles.formGroup}>
              <label className={styles.formLabel}>名称</label>
              <input
                className={styles.formInput}
                value={form.name}
                onChange={e => setForm(prev => ({ ...prev, name: e.target.value }))}
                placeholder="如：学术文献检索员"
              />
            </div>

            <div className={styles.formGroup}>
              <label className={styles.formLabel}>描述</label>
              <input
                className={styles.formInput}
                value={form.description}
                onChange={e => setForm(prev => ({ ...prev, description: e.target.value }))}
                placeholder="简要描述该智能体的职责"
              />
            </div>

            <div className={styles.formGroup}>
              <label className={styles.formLabel}>系统提示词</label>
              <textarea
                className={styles.formTextarea}
                value={form.system_prompt}
                onChange={e => setForm(prev => ({ ...prev, system_prompt: e.target.value }))}
                placeholder="定义该智能体的行为和角色..."
                rows={5}
              />
            </div>

            <div className={styles.formGroup}>
              <label className={styles.formLabel}>工具集</label>
              <div className={styles.toolsGrid}>
                {AVAILABLE_TOOLS.map(tool => (
                  <label
                    key={tool.value}
                    className={`${styles.toolCheckbox} ${
                      form.tools.includes(tool.value) ? styles.toolCheckboxActive : ''
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={form.tools.includes(tool.value)}
                      onChange={() => toggleTool(tool.value)}
                    />
                    {tool.label}
                  </label>
                ))}
              </div>
            </div>

            <div className={styles.modalActions}>
              <button className={styles.cancelBtn} onClick={() => setShowForm(false)}>
                取消
              </button>
              <button
                className={styles.submitBtn}
                disabled={!form.name.trim() || submitting}
                onClick={handleSubmit}
              >
                {submitting ? '保存中...' : editingId ? '更新' : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 删除确认弹窗 */}
      {deleteTarget && (
        <div className={styles.overlay} onClick={() => setDeleteTarget(null)}>
          <div className={styles.modal} onClick={e => e.stopPropagation()}>
            <h3 className={styles.modalTitle}>确认删除</h3>
            <p className={styles.confirmText}>
              确定要删除智能体 <span className={styles.confirmName}>{deleteTarget.name}</span> 吗？此操作不可撤销。
            </p>
            <div className={styles.modalActions}>
              <button className={styles.cancelBtn} onClick={() => setDeleteTarget(null)}>
                取消
              </button>
              <button className={styles.confirmDeleteBtn} onClick={handleDelete}>
                确认删除
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useState, useEffect, useCallback } from 'react';
import { modelConfigApi } from '../../api/modelConfigApi';
import styles from './ModelManager.module.css';

/* ===== 空态组件 ===== */
function EmptyState({ onAdd }) {
  return (
    <div className={styles.emptyState}>
      <div className={styles.emptyIcon}>
        <svg className={styles.emptyIconSvg} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
          <rect x="4" y="3" width="16" height="18" rx="2" />
          <line x1="8" y1="8" x2="16" y2="8" />
          <line x1="8" y1="12" x2="14" y2="12" />
          <line x1="8" y1="16" x2="11" y2="16" />
        </svg>
      </div>
      <p className={styles.emptyText}>暂无自定义模型，点击添加模型开始使用</p>
      <button className={styles.emptyAddBtn} onClick={onAdd}>添加</button>
    </div>
  );
}

/* ===== 模型卡片 ===== */
function ModelCard({ model, onActivate, onEdit, onDelete }) {
  const truncate = (str, max = 40) =>
    str && str.length > max ? str.slice(0, max) + '…' : (str || '—');

  return (
    <div className={`${styles.modelCard} ${model.is_active ? styles.active : ''}`}>
      <div className={styles.cardTop}>
        <span className={styles.modelName}>
          {model.display_name || model.model_name}
        </span>
        {model.is_active && (
          <span className={styles.activeBadge}>
            <span className={styles.activeDot} />
            使用中
          </span>
        )}
      </div>

      <div className={styles.cardMeta}>
        <div className={styles.metaRow}>
          <span className={styles.metaLabel}>模型：</span>
          <span className={styles.metaValue}>{model.model_name}</span>
        </div>
        {model.api_base_url && (
          <div className={styles.metaRow}>
            <span className={styles.metaLabel}>Base URL：</span>
            <span className={styles.metaValue}>{truncate(model.api_base_url, 42)}</span>
          </div>
        )}
        {model.api_key_masked && (
          <div className={styles.metaRow}>
            <span className={styles.metaLabel}>API Key：</span>
            <span className={styles.metaValue}>{model.api_key_masked}</span>
          </div>
        )}
      </div>

      <div className={styles.cardActions}>
        <button
          className={styles.actionBtnPrimary}
          onClick={() => onActivate(model.id)}
          disabled={model.is_active}
        >
          {model.is_active ? '已启用' : '使用此模型'}
        </button>
        <button className={styles.actionBtn} onClick={() => onEdit(model)}>
          编辑
        </button>
        <button className={styles.actionBtnDanger} onClick={() => onDelete(model)}>
          删除
        </button>
      </div>
    </div>
  );
}

/* ===== 添加/编辑弹窗 ===== */
function AddModelDialog({ model, onSubmit, onClose }) {
  const isEdit = !!model;

  const [form, setForm] = useState({
    display_name: model?.display_name || '',
    model_name: model?.model_name || '',
    api_base_url: model?.api_base_url || '',
    api_key: '',
  });
  const [showKey, setShowKey] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState({});

  const handleChange = (field, value) => {
    setForm(prev => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors(prev => ({ ...prev, [field]: '' }));
  };

  const validate = () => {
    const errs = {};
    if (!form.model_name.trim()) errs.model_name = '必填';
    if (!form.api_base_url.trim()) errs.api_base_url = '必填';
    if (!isEdit && !form.api_key.trim()) errs.api_key = '必填';
    return errs;
  };

  const handleSubmit = async () => {
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }

    setSubmitting(true);
    try {
      const data = { ...form };
      // 编辑时，如果 api_key 为空则不提交（保留原有密钥）
      if (isEdit && !data.api_key.trim()) {
        delete data.api_key;
      }
      if (!data.display_name.trim()) delete data.display_name;
      await onSubmit(data);
    } finally {
      setSubmitting(false);
    }
  };

  // ESC 关闭
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div className={styles.dialogOverlay} onClick={onClose}>
      <div className={styles.dialogCard} onClick={e => e.stopPropagation()}>
        {/* 标题栏 */}
        <div className={styles.dialogHeader}>
          <h3 className={styles.dialogTitle}>{isEdit ? '编辑模型' : '添加模型'}</h3>
          <button className={styles.dialogClose} onClick={onClose} title="关闭">×</button>
        </div>

        {/* 表单 */}
        <div className={styles.dialogBody}>
          {/* 显示名称（可选） */}
          <div className={styles.formField}>
            <label className={styles.fieldLabel}>显示名称</label>
            <input
              type="text"
              className={styles.fieldInput}
              placeholder="如 我的 DeepSeek（可选）"
              value={form.display_name}
              onChange={e => handleChange('display_name', e.target.value)}
            />
          </div>

          {/* Model Name（必填） */}
          <div className={styles.formField}>
            <label className={styles.fieldLabel}>
              Model Name <span className={styles.required}>*</span>
            </label>
            <input
              type="text"
              className={`${styles.fieldInput} ${errors.model_name ? styles.fieldInputError : ''}`}
              placeholder="如 deepseek-chat"
              value={form.model_name}
              onChange={e => handleChange('model_name', e.target.value)}
            />
            {errors.model_name && (
              <span style={{ fontSize: '12px', color: 'var(--color-danger)' }}>{errors.model_name}</span>
            )}
          </div>

          {/* API Base URL（必填） */}
          <div className={styles.formField}>
            <label className={styles.fieldLabel}>
              API Base URL <span className={styles.required}>*</span>
            </label>
            <input
              type="text"
              className={`${styles.fieldInput} ${errors.api_base_url ? styles.fieldInputError : ''}`}
              placeholder="如 https://api.deepseek.com"
              value={form.api_base_url}
              onChange={e => handleChange('api_base_url', e.target.value)}
            />
            {errors.api_base_url && (
              <span style={{ fontSize: '12px', color: 'var(--color-danger)' }}>{errors.api_base_url}</span>
            )}
          </div>

          {/* API Key（密码，必填/编辑时可选） */}
          <div className={styles.formField}>
            <label className={styles.fieldLabel}>
              API Key {!isEdit && <span className={styles.required}>*</span>}
              {isEdit && (
                <span style={{ fontSize: '11px', color: 'var(--color-text-muted)', fontWeight: 400 }}>
                  （留空保留原密钥）
                </span>
              )}
            </label>
            <div className={styles.passwordWrapper}>
              <input
                type={showKey ? 'text' : 'password'}
                className={`${styles.fieldInput} ${errors.api_key ? styles.fieldInputError : ''}`}
                placeholder="API 密钥"
                value={form.api_key}
                onChange={e => handleChange('api_key', e.target.value)}
              />
              <button
                type="button"
                className={styles.passwordToggle}
                onClick={() => setShowKey(v => !v)}
                title={showKey ? '隐藏' : '显示'}
              >
                {showKey ? (
                  /* 眼睛-划线（隐藏状态） */
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  /* 眼睛（可见状态） */
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
            {errors.api_key && (
              <span style={{ fontSize: '12px', color: 'var(--color-danger)' }}>{errors.api_key}</span>
            )}
          </div>
        </div>

        {/* 底部按钮 */}
        <div className={styles.dialogFooter}>
          <button className={styles.dialogCancelBtn} onClick={onClose} disabled={submitting}>
            取消
          </button>
          <button className={styles.dialogSubmitBtn} onClick={handleSubmit} disabled={submitting}>
            {submitting ? '提交中...' : (isEdit ? '保存' : '添加')}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ===== 主组件：ModelManager ===== */
export default function ModelManager() {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingModel, setEditingModel] = useState(null);

  const fetchModels = useCallback(async () => {
    try {
      setLoading(true);
      const resp = await modelConfigApi.getModels();
      setModels(resp.data?.models || []);
    } catch {
      // 错误已由拦截器弹 Toast
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModels();
  }, [fetchModels]);

  /* 激活模型 */
  const handleActivate = useCallback(async (id) => {
    try {
      await modelConfigApi.activateModel(id);
      await fetchModels();
    } catch {
      // handled by interceptor
    }
  }, [fetchModels]);

  /* 打开编辑弹窗 */
  const handleEdit = useCallback((model) => {
    setEditingModel(model);
    setShowDialog(true);
  }, []);

  /* 删除模型 */
  const handleDelete = useCallback(async (model) => {
    const name = model.display_name || model.model_name;
    if (!window.confirm(`确认删除模型「${name}」？此操作不可恢复。`)) return;
    try {
      await modelConfigApi.deleteModel(model.id);
      await fetchModels();
    } catch {
      // handled by interceptor
    }
  }, [fetchModels]);

  /* 提交（新增或编辑） */
  const handleSubmit = useCallback(async (data) => {
    try {
      if (editingModel) {
        await modelConfigApi.updateModel(editingModel.id, data);
      } else {
        await modelConfigApi.addModel(data);
      }
      setShowDialog(false);
      setEditingModel(null);
      await fetchModels();
    } catch {
      // handled by interceptor — re-throw so dialog keeps open
      throw new Error('submit failed');
    }
  }, [editingModel, fetchModels]);

  const handleCloseDialog = useCallback(() => {
    setShowDialog(false);
    setEditingModel(null);
  }, []);

  return (
    <div className={styles.container}>
      {/* 标题栏 */}
      <div className={styles.managerHeader}>
        <div>
          <h2 className={styles.managerTitle}>模型</h2>
          <p className={styles.managerDesc}>
            使用自有 API Key 管理自定义模型。
          </p>
        </div>
        <button className={styles.addBtn} onClick={() => setShowDialog(true)}>
          + 添加
        </button>
      </div>

      {/* 列表区域 */}
      <div className={styles.listArea}>
        {loading ? (
          <div className={styles.loadingState}>
            <span className={styles.spinner} />
            加载中...
          </div>
        ) : models.length === 0 ? (
          <EmptyState onAdd={() => setShowDialog(true)} />
        ) : (
          <div className={styles.modelList}>
            {models.map(m => (
              <ModelCard
                key={m.id}
                model={m}
                onActivate={handleActivate}
                onEdit={handleEdit}
                onDelete={handleDelete}
              />
            ))}
          </div>
        )}
      </div>

      {/* 添加/编辑弹窗 */}
      {showDialog && (
        <AddModelDialog
          model={editingModel}
          onSubmit={handleSubmit}
          onClose={handleCloseDialog}
        />
      )}
    </div>
  );
}

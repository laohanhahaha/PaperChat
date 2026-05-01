import React, { useEffect, useRef, useState } from 'react';
import { modelConfigApi } from '../../api/modelConfigApi';
import styles from './ModelSelector.module.css';

export default function ModelSelector() {
  const [models, setModels] = useState([]);
  const [activeModel, setActiveModel] = useState(null);
  const [loading, setLoading] = useState({ list: false, switching: false });
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // 获取用户自定义模型列表
  const fetchModels = async () => {
    setLoading(prev => ({ ...prev, list: true }));
    try {
      const res = await modelConfigApi.getModels();
      const list = res.data?.models || [];
      setModels(list);
      const active = list.find(m => m.is_active);
      setActiveModel(active || null);
    } catch (e) {
      // 静默失败
    } finally {
      setLoading(prev => ({ ...prev, list: false }));
    }
  };

  useEffect(() => {
    fetchModels();
  }, []);

  // 点击外部关闭
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSwitch = async (modelId) => {
    if (modelId === activeModel?.id) { setOpen(false); return; }
    setLoading(prev => ({ ...prev, switching: true }));
    try {
      await modelConfigApi.activateModel(modelId);
      await fetchModels();
    } catch (e) {
      // toast handled in api interceptor
    } finally {
      setLoading(prev => ({ ...prev, switching: false }));
      setOpen(false);
    }
  };

  const displayName = activeModel
    ? (activeModel.display_name || activeModel.model_name)
    : (models.length === 0 ? '无可用模型' : '选择模型');

  return (
    <div className={styles.wrapper} ref={ref}>
      <button
        className={styles.trigger}
        onClick={() => setOpen(v => !v)}
        disabled={loading.switching || loading.list}
        title={activeModel?.model_name || ''}
      >
        <span className={styles.icon}>⚡</span>
        <span className={styles.label}>{loading.switching ? '切换中…' : displayName}</span>
        <span className={styles.arrow}>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className={styles.dropdown}>
          <div className={styles.dropdownHeader}>选择模型</div>
          {models.length === 0 ? (
            <div className={styles.emptyTip}>请先在设置中添加模型</div>
          ) : (
            models.map(m => {
              const active = m.id === activeModel?.id;
              return (
                <button
                  key={m.id}
                  className={`${styles.option} ${active ? styles.optionActive : ''}`}
                  onClick={() => handleSwitch(m.id)}
                >
                  <div className={styles.optionTop}>
                    <span className={styles.optionName}>{m.display_name || m.model_name}</span>
                    {active && <span className={styles.activeDot}>●</span>}
                  </div>
                  <div className={styles.optionDesc}>{m.model_name}</div>
                  {m.api_base_url && (
                    <div className={styles.optionPrice}>{m.api_base_url}</div>
                  )}
                </button>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}

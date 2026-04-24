import React, { useEffect, useRef, useState } from 'react';
import { useCostStore } from '../../stores/costStore';
import styles from './ModelSelector.module.css';

export default function ModelSelector() {
  const { models, currentModel, loading, fetchModels, fetchCurrentModel, switchModel } = useCostStore();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    fetchModels();
    fetchCurrentModel();
  }, [fetchModels, fetchCurrentModel]);

  // 点击外部关闭
  useEffect(() => {
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSwitch = async (modelName) => {
    if (modelName === currentModel?.model) { setOpen(false); return; }
    try {
      await switchModel(modelName);
    } catch (e) {
      // toast handled in api interceptor
    }
    setOpen(false);
  };

  const displayName = currentModel?.model ?? '选择模型';
  const short = displayName.replace('deepseek-', '');

  return (
    <div className={styles.wrapper} ref={ref}>
      <button
        className={styles.trigger}
        onClick={() => setOpen(v => !v)}
        disabled={loading.switching}
        title={currentModel?.description}
      >
        <span className={styles.icon}>⚡</span>
        <span className={styles.label}>{loading.switching ? '切换中…' : short}</span>
        <span className={styles.arrow}>{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className={styles.dropdown}>
          <div className={styles.dropdownHeader}>选择模型</div>
          {models.map(m => {
            const active = m.name === currentModel?.model;
            return (
              <button
                key={m.name}
                className={`${styles.option} ${active ? styles.optionActive : ''}`}
                onClick={() => handleSwitch(m.name)}
              >
                <div className={styles.optionTop}>
                  <span className={styles.optionName}>{m.name.replace('deepseek-', '')}</span>
                  {active && <span className={styles.activeDot}>●</span>}
                </div>
                <div className={styles.optionDesc}>{m.description}</div>
                <div className={styles.optionPrice}>
                  输入 ${m.input_price_per_1m}/M · 输出 ${m.output_price_per_1m}/M
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

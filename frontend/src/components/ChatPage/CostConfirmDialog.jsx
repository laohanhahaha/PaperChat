import React from 'react';

/**
 * 费用确认弹窗 — 预估费用超阈值时显示（智能路由专用）
 * 与 Cost/CostConfirmDialog 不同，此弹窗专注于模型路由场景，
 * 支持推荐模型展示和降级选项
 * @param {boolean} open - 是否显示
 * @param {string} model - 推荐模型
 * @param {number} estimatedCost - 预估费用
 * @param {string} message - 提示消息
 * @param {function} onConfirm - 确认回调
 * @param {function} onCancel - 取消（降级）回调
 */
export default function CostConfirmDialog({ open, model, estimatedCost, message, onConfirm, onCancel }) {
  if (!open) return null;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: 'rgba(0,0,0,0.4)',
      zIndex: 10000,
    }}>
      <div style={{
        backgroundColor: 'var(--bg-primary, #fff)',
        borderRadius: '12px',
        padding: '24px',
        maxWidth: '400px',
        width: '90%',
        boxShadow: '0 8px 32px rgba(0,0,0,0.12)',
      }}>
        <h3 style={{ margin: '0 0 12px', fontSize: '16px' }}>费用确认</h3>
        <p style={{ margin: '0 0 8px', color: '#666', fontSize: '14px' }}>
          {message || `此操作预估费用 ¥${(estimatedCost || 0).toFixed(2)}`}
        </p>
        <p style={{ margin: '0 0 16px', color: '#999', fontSize: '13px' }}>
          推荐模型: {model}
        </p>
        <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
          <button
            onClick={onCancel}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: '1px solid #d9d9d9',
              backgroundColor: 'transparent',
              cursor: 'pointer',
              fontSize: '14px',
            }}
          >
            使用免费模型
          </button>
          <button
            onClick={onConfirm}
            style={{
              padding: '8px 16px',
              borderRadius: '6px',
              border: 'none',
              backgroundColor: '#1890ff',
              color: '#fff',
              cursor: 'pointer',
              fontSize: '14px',
            }}
          >
            确认使用 (¥{(estimatedCost || 0).toFixed(2)})
          </button>
        </div>
      </div>
    </div>
  );
}

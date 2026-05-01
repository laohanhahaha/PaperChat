import React from 'react';

/**
 * 模型标识组件 — 每条消息旁显示所用模型
 * @param {string} model - 模型名称
 * @param {string} tier - local_light|local_medium|cloud_standard|cloud_premium
 * @param {number} estimatedCost - 预估费用
 * @param {boolean} privacyEnforced - 是否因隐私保护强制本地处理
 */
export default function ModelIndicator({ model, tier, estimatedCost, privacyEnforced }) {
  // 隐私强制本地处理时显示特殊标识
  if (privacyEnforced) {
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          fontSize: '12px',
          color: '#fa8c16',
          padding: '2px 6px',
          borderRadius: '4px',
          backgroundColor: '#fa8c1610',
        }}
        title={`${model || '本地模型'} — 隐私保护：数据不离开本机`}
      >
        <span>🔒</span>
        <span style={{ color: '#fa8c16' }}>本地处理（隐私保护）</span>
      </span>
    );
  }

  const isLocal = tier?.startsWith('local');
  const icon = isLocal ? '🏠' : '☁️';
  const label = isLocal ? '本地' : '云端';
  const color = isLocal ? '#52c41a' : '#1890ff';

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        fontSize: '12px',
        color: '#999',
        padding: '2px 6px',
        borderRadius: '4px',
        backgroundColor: `${color}10`,
      }}
      title={`${model || '未知模型'} | 预估费用: ¥${(estimatedCost || 0).toFixed(3)}`}
    >
      <span>{icon}</span>
      <span style={{ color }}>{label}</span>
      {estimatedCost > 0 && (
        <span style={{ color: '#999' }}>¥{estimatedCost.toFixed(3)}</span>
      )}
    </span>
  );
}

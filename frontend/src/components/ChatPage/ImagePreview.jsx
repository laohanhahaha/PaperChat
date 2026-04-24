import React from 'react';
import styles from './ImagePreview.module.css';

/**
 * 图片预览组件 - 三态状态管理
 * @param {Array} images - 图片列表 [{file, status, image_id, progress, error, thumbnailUrl}]
 * @param {Function} onRemove - 移除图片回调 (index) => void
 */
export default function ImagePreview({ images, onRemove }) {
  if (!images || !images.length) return null;

  return (
    <div className={styles.imageGrid}>
      {images.map((img, idx) => (
        <div key={idx} className={styles.imageItem}>
          {img.status === 'uploading' && (
            <div className={styles.uploading}>
              <div className={styles.progressTrack}>
                <div
                  className={styles.progressBar}
                  style={{ width: `${img.progress || 0}%` }}
                />
              </div>
              <span className={styles.progressText}>{img.progress || 0}%</span>
            </div>
          )}
          {img.status === 'ready' && (
            <div className={styles.ready}>
              <img
                src={img.thumbnailUrl}
                alt={img.file?.name || '图片'}
                className={styles.thumbnail}
              />
              <button
                onClick={() => onRemove(idx)}
                className={styles.removeBtn}
                title="移除"
              >
                ×
              </button>
            </div>
          )}
          {img.status === 'error' && (
            <div className={styles.error}>
              <span className={styles.errorText}>上传失败</span>
              {img.onRetry && (
                <button
                  onClick={() => img.onRetry()}
                  className={styles.retryBtn}
                >
                  重试
                </button>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

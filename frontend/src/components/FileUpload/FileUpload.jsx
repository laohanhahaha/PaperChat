import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import usePaperStore from '../../stores/paperStore';
import styles from './FileUpload.module.css';

function FileUpload({ onFileSelect, onUploadSuccess }) {
  const { uploadPaper } = usePaperStore();
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState(null);

  const onDrop = useCallback(async (acceptedFiles) => {
    if (acceptedFiles.length === 0) return;
    
    const file = acceptedFiles[0];
    
    // 如果提供了 onFileSelect 回调（旧模式），直接调用
    if (onFileSelect) {
      onFileSelect(file);
      return;
    }
    
    // 新模式：上传到后端
    setUploading(true);
    setUploadProgress(0);
    setError(null);
    
    try {
      const paper = await uploadPaper(file, {
        title: file.name.replace('.pdf', ''),
      });
      
      if (onUploadSuccess) {
        onUploadSuccess(paper);
      }
    } catch (err) {
      console.error('上传失败:', err);
      setError(err.response?.data?.detail || '上传失败，请重试');
    } finally {
      setUploading(false);
    }
  }, [onFileSelect, onUploadSuccess, uploadPaper]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxSize: 50 * 1024 * 1024,
    multiple: false,
    disabled: uploading,
  });

  return (
    <div className={styles.container}>
      <div 
        {...getRootProps()} 
        className={`${styles.dropzone} ${isDragActive ? styles.active : ''} ${uploading ? styles.disabled : ''}`}
      >
        <input {...getInputProps()} />
        
        {uploading ? (
          <div className={styles.uploading}>
            <div className={styles.spinner}></div>
            <p className={styles.title}>正在上传...</p>
            <div className={styles.progressBar}>
              <div 
                className={styles.progressFill} 
                style={{ width: `${uploadProgress}%` }}
              ></div>
            </div>
          </div>
        ) : (
          <div className={styles.content}>
            <div className={styles.icon}>📄</div>
            <h3 className={styles.title}>
              {isDragActive ? '释放文件' : '拖拽PDF文件到此处'}
            </h3>
            <p className={styles.subtitle}>或点击选择文件（最大50MB）</p>
          </div>
        )}
      </div>
      
      {error && (
        <div className={styles.error}>
          {error}
        </div>
      )}
    </div>
  );
}

export default FileUpload;

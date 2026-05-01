import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import usePaperStore from '../../stores/paperStore';
import { paperApi } from '../../api/paperApi';
import styles from './BatchImport.module.css';

// Tab 类型
const TABS = {
  BATCH: 'batch',
  ZIP: 'zip',
  SCAN: 'scan',
};

// 扫描步骤
const SCAN_STEPS = {
  INPUT: 'input',
  RESULT: 'result',
  IMPORTING: 'importing',
  DONE: 'done',
};

// 格式化文件大小
const formatFileSize = (bytes) => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
};

function BatchImport({ onClose, onSuccess }) {
  const [activeTab, setActiveTab] = useState(TABS.BATCH);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);

  const { batchUpload, batchUploadZip } = usePaperStore();

  // ========== 批量上传 Tab ==========
  const [batchFiles, setBatchFiles] = useState([]);

  const onBatchDrop = useCallback((acceptedFiles) => {
    const pdfFiles = acceptedFiles.filter(file => 
      file.name.toLowerCase().endsWith('.pdf')
    );
    setBatchFiles(prev => [...prev, ...pdfFiles]);
    setUploadResult(null);
  }, []);

  const { getRootProps: getBatchRootProps, getInputProps: getBatchInputProps, isDragActive: isBatchDragActive } = useDropzone({
    onDrop: onBatchDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxSize: 50 * 1024 * 1024,
    multiple: true,
  });

  const removeBatchFile = (index) => {
    setBatchFiles(prev => prev.filter((_, i) => i !== index));
  };

  const handleBatchUpload = async () => {
    if (batchFiles.length === 0) return;
    
    setIsUploading(true);
    setUploadProgress(0);
    setUploadResult(null);
    
    try {
      const result = await batchUpload(batchFiles, (progress) => {
        setUploadProgress(progress);
      });
      setUploadResult(result);
      setBatchFiles([]);
      if (onSuccess && result.success > 0) onSuccess();
    } catch (err) {
      console.error('批量上传失败:', err);
    } finally {
      setIsUploading(false);
    }
  };

  // ========== 扫描文件夹 Tab ==========
  const [scanStep, setScanStep] = useState(SCAN_STEPS.INPUT);
  const [folderPath, setFolderPath] = useState('');
  const [recursive, setRecursive] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [selectedFiles, setSelectedFiles] = useState(new Set());
  const [isImporting, setIsImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [showImportDetails, setShowImportDetails] = useState(false);
  const [scanError, setScanError] = useState(null);

  const handleScanFolder = async () => {
    if (!folderPath.trim()) return;
    setIsScanning(true);
    setScanError(null);
    setScanResult(null);
    try {
      const response = await paperApi.scanFolder(folderPath.trim(), recursive);
      const data = response.data;
      setScanResult(data);
      // 默认勾选所有 new 文件
      const newFileIndices = new Set();
      data.files.forEach((f, i) => {
        if (f.status === 'new') newFileIndices.add(i);
      });
      setSelectedFiles(newFileIndices);
      setScanStep(SCAN_STEPS.RESULT);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || '扫描失败';
      setScanError(msg);
    } finally {
      setIsScanning(false);
    }
  };

  const toggleFileSelection = (index) => {
    setSelectedFiles(prev => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const toggleSelectAllNew = () => {
    if (!scanResult) return;
    const newIndices = scanResult.files
      .map((f, i) => (f.status === 'new' ? i : -1))
      .filter(i => i !== -1);
    const allSelected = newIndices.every(i => selectedFiles.has(i));
    setSelectedFiles(prev => {
      const next = new Set(prev);
      if (allSelected) {
        newIndices.forEach(i => next.delete(i));
      } else {
        newIndices.forEach(i => next.add(i));
      }
      return next;
    });
  };

  const handleImportSelected = async () => {
    if (!scanResult || selectedFiles.size === 0) return;
    const paths = Array.from(selectedFiles).map(i => scanResult.files[i].path);
    setIsImporting(true);
    setImportResult(null);
    setScanStep(SCAN_STEPS.IMPORTING);
    try {
      const response = await paperApi.importFolder(paths);
      setImportResult(response.data);
      setScanStep(SCAN_STEPS.DONE);
      if (onSuccess && response.data.imported > 0) onSuccess();
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || '导入失败';
      setScanError(msg);
      setScanStep(SCAN_STEPS.RESULT);
    } finally {
      setIsImporting(false);
    }
  };

  const handleScanReset = () => {
    setScanStep(SCAN_STEPS.INPUT);
    setScanResult(null);
    setSelectedFiles(new Set());
    setImportResult(null);
    setScanError(null);
    setShowImportDetails(false);
  };

  // ========== ZIP 导入 Tab ==========
  const [zipFile, setZipFile] = useState(null);

  const onZipDrop = useCallback((acceptedFiles) => {
    if (acceptedFiles.length > 0) {
      const file = acceptedFiles[0];
      if (file.name.toLowerCase().endsWith('.zip')) {
        setZipFile(file);
        setUploadResult(null);
      }
    }
  }, []);

  const { getRootProps: getZipRootProps, getInputProps: getZipInputProps, isDragActive: isZipDragActive } = useDropzone({
    onDrop: onZipDrop,
    accept: { 'application/zip': ['.zip'] },
    maxSize: 100 * 1024 * 1024,
    multiple: false,
  });

  const removeZipFile = () => {
    setZipFile(null);
  };

  const handleZipUpload = async () => {
    if (!zipFile) return;
    
    setIsUploading(true);
    setUploadProgress(0);
    setUploadResult(null);
    
    try {
      const result = await batchUploadZip(zipFile, (progress) => {
        setUploadProgress(progress);
      });
      setUploadResult(result);
      setZipFile(null);
      if (onSuccess && result.success > 0) onSuccess();
    } catch (err) {
      console.error('ZIP 导入失败:', err);
    } finally {
      setIsUploading(false);
    }
  };

  // 渲染批量上传 Tab
  const renderBatchTab = () => (
    <div className={styles.tabContent}>
      <div
        {...getBatchRootProps()}
        className={`${styles.dropzone} ${isBatchDragActive ? styles.active : ''} ${isUploading ? styles.disabled : ''}`}
      >
        <input {...getBatchInputProps()} disabled={isUploading} />
        <div className={styles.dropzoneIcon}>📄</div>
        <p className={styles.dropzoneText}>
          {isBatchDragActive ? '释放文件以上传' : '拖拽 PDF 文件到此处'}
        </p>
        <p className={styles.dropzoneHint}>或点击选择多个文件（最大 50MB/文件）</p>
      </div>

      {batchFiles.length > 0 && (
        <div className={styles.fileList}>
          <div className={styles.fileListHeader}>
            <span>已选择 {batchFiles.length} 个文件</span>
            <button 
              className={styles.clearBtn}
              onClick={() => setBatchFiles([])}
              disabled={isUploading}
            >
              清空
            </button>
          </div>
          <div className={styles.fileItems}>
            {batchFiles.map((file, index) => (
              <div key={index} className={styles.fileItem}>
                <span className={styles.fileName}>{file.name}</span>
                <span className={styles.fileSize}>{formatFileSize(file.size)}</span>
                <button
                  className={styles.removeBtn}
                  onClick={() => removeBatchFile(index)}
                  disabled={isUploading}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {isUploading && (
        <div className={styles.progressContainer}>
          <div className={styles.progressBar}>
            <div 
              className={styles.progressFill} 
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
          <span className={styles.progressText}>{uploadProgress}%</span>
        </div>
      )}

      {uploadResult && activeTab === TABS.BATCH && (
        <div className={`${styles.resultBox} ${uploadResult.failed === 0 ? styles.success : styles.partial}`}>
          <div className={styles.resultSummary}>
            <span className={styles.resultTotal}>总计: {uploadResult.total}</span>
            <span className={styles.resultSuccess}>成功: {uploadResult.success}</span>
            {uploadResult.failed > 0 && (
              <span className={styles.resultFailed}>失败: {uploadResult.failed}</span>
            )}
          </div>
          {uploadResult.results && uploadResult.results.some(r => r.status === 'error') && (
            <div className={styles.errorList}>
              <p className={styles.errorTitle}>失败详情:</p>
              {uploadResult.results
                .filter(r => r.status === 'error')
                .map((r, i) => (
                  <div key={i} className={styles.errorItem}>
                    <span className={styles.errorFile}>{r.filename}</span>
                    <span className={styles.errorMsg}>{r.message}</span>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}

      <button
        className={styles.uploadBtn}
        onClick={handleBatchUpload}
        disabled={batchFiles.length === 0 || isUploading}
      >
        {isUploading ? '上传中...' : `上传 ${batchFiles.length} 个文件`}
      </button>
    </div>
  );

  // 渲染 ZIP 导入 Tab
  const renderZipTab = () => (
    <div className={styles.tabContent}>
      <div className={styles.zipHint}>
        <svg className={styles.hintIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <span>ZIP 中的 PDF 文件将被自动提取并导入</span>
      </div>

      {!zipFile ? (
        <div
          {...getZipRootProps()}
          className={`${styles.dropzone} ${isZipDragActive ? styles.active : ''} ${isUploading ? styles.disabled : ''}`}
        >
          <input {...getZipInputProps()} disabled={isUploading} />
          <div className={styles.dropzoneIcon}>🗜️</div>
          <p className={styles.dropzoneText}>
            {isZipDragActive ? '释放 ZIP 文件' : '拖拽 ZIP 文件到此处'}
          </p>
          <p className={styles.dropzoneHint}>或点击选择文件（最大 100MB）</p>
        </div>
      ) : (
        <div className={styles.zipFileBox}>
          <div className={styles.zipFileInfo}>
            <span className={styles.zipFileIcon}>🗜️</span>
            <div className={styles.zipFileDetails}>
              <span className={styles.zipFileName}>{zipFile.name}</span>
              <span className={styles.zipFileSize}>{formatFileSize(zipFile.size)}</span>
            </div>
          </div>
          <button
            className={styles.removeBtn}
            onClick={removeZipFile}
            disabled={isUploading}
          >
            ×
          </button>
        </div>
      )}

      {isUploading && (
        <div className={styles.progressContainer}>
          <div className={styles.progressBar}>
            <div 
              className={styles.progressFill} 
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
          <span className={styles.progressText}>{uploadProgress}%</span>
        </div>
      )}

      {uploadResult && activeTab === TABS.ZIP && (
        <div className={`${styles.resultBox} ${uploadResult.failed === 0 ? styles.success : styles.partial}`}>
          <div className={styles.resultSummary}>
            <span className={styles.resultTotal}>总计: {uploadResult.total}</span>
            <span className={styles.resultSuccess}>成功: {uploadResult.success}</span>
            {uploadResult.failed > 0 && (
              <span className={styles.resultFailed}>失败: {uploadResult.failed}</span>
            )}
          </div>
          {uploadResult.results && uploadResult.results.some(r => r.status === 'error') && (
            <div className={styles.errorList}>
              <p className={styles.errorTitle}>失败详情:</p>
              {uploadResult.results
                .filter(r => r.status === 'error')
                .map((r, i) => (
                  <div key={i} className={styles.errorItem}>
                    <span className={styles.errorFile}>{r.filename}</span>
                    <span className={styles.errorMsg}>{r.message}</span>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}

      <button
        className={styles.uploadBtn}
        onClick={handleZipUpload}
        disabled={!zipFile || isUploading}
      >
        {isUploading ? '导入中...' : '导入 ZIP 文件'}
      </button>
    </div>
  );

  // 渲染扫描文件夹 Tab
  const renderScanTab = () => {
    // 扫描输入阶段
    if (scanStep === SCAN_STEPS.INPUT) {
      return (
        <div className={styles.tabContent}>
          <div className={styles.scanHint}>
            <svg className={styles.hintIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>扫描本地文件夹中的 PDF 文件，自动去重后导入</span>
          </div>

          <div className={styles.scanInputGroup}>
            <input
              type="text"
              className={styles.scanInput}
              placeholder="输入本地文件夹路径，如 D:/papers/"
              value={folderPath}
              onChange={(e) => setFolderPath(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleScanFolder()}
              disabled={isScanning}
            />
          </div>

          <label className={styles.scanCheckbox}>
            <input
              type="checkbox"
              checked={recursive}
              onChange={(e) => setRecursive(e.target.checked)}
              disabled={isScanning}
            />
            <span>递归扫描子目录</span>
          </label>

          {scanError && (
            <div className={styles.scanErrorBox}>{scanError}</div>
          )}

          <button
            className={styles.uploadBtn}
            onClick={handleScanFolder}
            disabled={!folderPath.trim() || isScanning}
          >
            {isScanning ? (
              <span className={styles.scanBtnLoading}>
                <span className={styles.spinner} /> 扫描中...
              </span>
            ) : '开始扫描'}
          </button>
        </div>
      );
    }

    // 扫描结果阶段
    if (scanStep === SCAN_STEPS.RESULT) {
      const files = scanResult?.files || [];
      const newCount = files.filter(f => f.status === 'new').length;
      const existsCount = files.filter(f => f.status === 'exists').length;
      const newIndices = files.map((f, i) => (f.status === 'new' ? i : -1)).filter(i => i !== -1);
      const allNewSelected = newIndices.length > 0 && newIndices.every(i => selectedFiles.has(i));

      return (
        <div className={styles.tabContent}>
          <div className={styles.scanStats}>
            <span>共发现 <strong>{files.length}</strong> 个 PDF</span>
            <span className={styles.scanStatNew}>{newCount} 个新文件</span>
            <span className={styles.scanStatExists}>{existsCount} 个已存在</span>
          </div>

          {scanError && (
            <div className={styles.scanErrorBox}>{scanError}</div>
          )}

          <div className={styles.scanTable}>
            <div className={styles.scanTableHeader}>
              <label className={styles.scanTableCheck}>
                <input
                  type="checkbox"
                  checked={allNewSelected}
                  onChange={toggleSelectAllNew}
                />
              </label>
              <span className={styles.scanTableColName}>文件名</span>
              <span className={styles.scanTableColSize}>大小</span>
              <span className={styles.scanTableColStatus}>状态</span>
            </div>
            <div className={styles.scanTableBody}>
              {files.map((file, index) => {
                const isExists = file.status === 'exists';
                return (
                  <div
                    key={index}
                    className={`${styles.scanTableRow} ${isExists ? styles.scanRowDisabled : ''}`}
                  >
                    <label className={styles.scanTableCheck}>
                      <input
                        type="checkbox"
                        checked={selectedFiles.has(index)}
                        onChange={() => toggleFileSelection(index)}
                        disabled={isExists}
                      />
                    </label>
                    <span className={styles.scanTableColName} title={file.path}>
                      {file.filename}
                    </span>
                    <span className={styles.scanTableColSize}>
                      {file.size_mb != null ? file.size_mb.toFixed(1) + ' MB' : '-'}
                    </span>
                    <span className={styles.scanTableColStatus}>
                      {isExists ? (
                        <span className={styles.statusTagExists}>已存在</span>
                      ) : (
                        <span className={styles.statusTagNew}>新文件</span>
                      )}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className={styles.scanActions}>
            <button
              className={styles.scanBackBtn}
              onClick={handleScanReset}
            >
              返回
            </button>
            <button
              className={styles.uploadBtn}
              onClick={handleImportSelected}
              disabled={selectedFiles.size === 0}
              style={{ flex: 1 }}
            >
              导入选中文件（{selectedFiles.size}）
            </button>
          </div>
        </div>
      );
    }

    // 导入中阶段
    if (scanStep === SCAN_STEPS.IMPORTING) {
      return (
        <div className={styles.tabContent}>
          <div className={styles.loadingIndicator}>
            <div className={styles.spinner} />
            <span>正在导入 {selectedFiles.size} 个文件...</span>
          </div>
          <div className={styles.progressContainer}>
            <div className={styles.progressBar}>
              <div className={`${styles.progressFill} ${styles.progressIndeterminate}`} />
            </div>
          </div>
        </div>
      );
    }

    // 导入完成阶段
    if (scanStep === SCAN_STEPS.DONE && importResult) {
      const r = importResult;
      const allSuccess = r.failed === 0;
      return (
        <div className={styles.tabContent}>
          <div className={`${styles.resultBox} ${allSuccess ? styles.success : styles.partial}`}>
            <div className={styles.resultSummary}>
              <span className={styles.resultSuccess}>成功导入: {r.imported}</span>
              {r.skipped > 0 && <span className={styles.resultWarning}>已跳过: {r.skipped}</span>}
              {r.failed > 0 && <span className={styles.resultFailed}>失败: {r.failed}</span>}
            </div>
          </div>

          {r.details && r.details.length > 0 && (
            <div className={styles.scanDetailsToggle}>
              <button
                className={styles.clearBtn}
                onClick={() => setShowImportDetails(!showImportDetails)}
              >
                {showImportDetails ? '收起详情 ▲' : '展开详情 ▼'}
              </button>
            </div>
          )}

          {showImportDetails && r.details && (
            <div className={styles.scanDetailsList}>
              {r.details.map((d, i) => (
                <div key={i} className={styles.scanDetailItem}>
                  <span className={styles.scanDetailName}>{d.filename}</span>
                  <span className={
                    d.status === 'success' ? styles.scanDetailSuccess :
                    d.status === 'skipped' ? styles.scanDetailSkipped :
                    styles.scanDetailError
                  }>
                    {d.status === 'success' ? '成功' : d.status === 'skipped' ? '跳过' : '失败'}
                  </span>
                  {d.message && <span className={styles.scanDetailMsg}>{d.message}</span>}
                </div>
              ))}
            </div>
          )}

          <button
            className={styles.uploadBtn}
            onClick={handleScanReset}
          >
            返回
          </button>
        </div>
      );
    }

    return null;
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h3 className={styles.title}>批量导入论文</h3>
          <button className={styles.closeBtn} onClick={onClose}>×</button>
        </div>

        <div className={styles.tabs}>
          <button
            className={`${styles.tab} ${activeTab === TABS.BATCH ? styles.active : ''}`}
            onClick={() => setActiveTab(TABS.BATCH)}
          >
            <svg className={styles.tabIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            批量上传
          </button>
          <button
            className={`${styles.tab} ${activeTab === TABS.ZIP ? styles.active : ''}`}
            onClick={() => setActiveTab(TABS.ZIP)}
          >
            <svg className={styles.tabIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4" />
            </svg>
            ZIP 导入
          </button>
          <button
            className={`${styles.tab} ${activeTab === TABS.SCAN ? styles.active : ''}`}
            onClick={() => setActiveTab(TABS.SCAN)}
          >
            <svg className={styles.tabIcon} viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
            扫描文件夹
          </button>
        </div>

        <div className={styles.content}>
          {activeTab === TABS.BATCH && renderBatchTab()}
          {activeTab === TABS.ZIP && renderZipTab()}
          {activeTab === TABS.SCAN && renderScanTab()}
        </div>
      </div>
    </div>
  );
}

export default BatchImport;

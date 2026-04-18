import { useEffect, useRef, useState } from 'react';
import MarkdownContent from '../../utils/MarkdownRenderer';
import styles from './ExplanationPanel.module.css';

// 维度图标映射
const dimensionIcons = {
  overview: '📋',
  research_question: '🔬',
  methodology: '⚙️',
  results: '📊',
  contributions: '💡',
  limitations: '⚠️',
  knowledge_point: '🎯',
};

function ExplanationPanel({ 
  pdfText, 
  explanations, 
  deepAnalysis,
  isAnalyzing, 
  isDeepAnalyzing,
  keywords = [],  // 新增
}) {
  const containerRef = useRef(null);
  
  // 本地状态
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'deep' | 'keywords'
  const [expandedDimensions, setExpandedDimensions] = useState(new Set());
  const [expandedKnowledgePoints, setExpandedKnowledgePoints] = useState(new Set());

  // 自动滚动到底部
  useEffect(() => {
    if (containerRef.current && activeTab === 'overview') {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [explanations, activeTab]);

  const getTypeLabel = (type) => {
    const map = {
      title: '标题',
      abstract: '摘要',
      section: '章节',
      subsection: '小节',
    };
    return map[type] || '内容';
  };

  // 切换维度展开/折叠
  const toggleDimension = (dimension) => {
    setExpandedDimensions(prev => {
      const newSet = new Set(prev);
      if (newSet.has(dimension)) {
        newSet.delete(dimension);
      } else {
        newSet.add(dimension);
      }
      return newSet;
    });
  };

  // 切换知识点展开/折叠
  const toggleKnowledgePoint = (index) => {
    setExpandedKnowledgePoints(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  // 导出分析报告
  const handleExportReport = () => {
    if (!deepAnalysis || deepAnalysis.dimensions.length === 0) return;
    
    let markdown = '# 论文深度分析报告\n\n';
    
    deepAnalysis.dimensions.forEach(dim => {
      markdown += `## ${dim.title}\n\n${dim.content}\n\n`;
    });
    
    if (deepAnalysis.knowledgePoints.length > 0) {
      markdown += '## 核心知识点\n\n';
      deepAnalysis.knowledgePoints.forEach((kp, index) => {
        markdown += `### ${kp.title || `知识点 ${index + 1}`}\n\n${kp.content}\n\n`;
      });
    }
    
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `论文深度分析报告_${new Date().toLocaleDateString()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // 渲染章节概览Tab
  const renderOverviewTab = () => {
    if (!pdfText) {
      return (
        <div className={styles.empty}>
          <p>上传PDF后可进行章节概述分析</p>
        </div>
      );
    }

    const hasExplanations = explanations.length > 0;

    return (
      <div className={styles.tabContent} ref={containerRef}>
        {!hasExplanations && !isAnalyzing && (
          <div className={styles.empty}>
            <p className={styles.emptyIcon}>📭</p>
            <p className={styles.emptyTitle}>尚未生成章节概述</p>
            <p className={styles.emptyHint}>点击上方「章节概述」按钮开始分析</p>
          </div>
        )}
        {explanations.map((item, index) => (
          <div key={index} className={styles.card}>
            <div className={styles.cardHeader}>
              <span className={styles.typeTag}>{getTypeLabel(item.type)}</span>
              <span className={styles.sectionName}>{item.section}</span>
            </div>
            <MarkdownContent content={item.explanation} className={styles.explanation} />
          </div>
        ))}
        {isAnalyzing && (
          <div className={styles.loading}>
            <div className={styles.spinner}></div>
            <span>正在分析论文...</span>
          </div>
        )}
      </div>
    );
  };

  // 渲染关键词Tab
  const renderKeywordsTab = () => {
    if (keywords.length === 0) {
      return (
        <div className={styles.empty}>
          <p className={styles.emptyIcon}>🏷️</p>
          <p className={styles.emptyTitle}>尚未提取关键词</p>
          <p className={styles.emptyHint}>点击上方「章节概述」或「深度分析」按钮后自动提取</p>
        </div>
      );
    }

    return (
      <div className={styles.tabContent}>
        <div className={styles.keywordsContainer}>
          {keywords.map((keyword, index) => (
            <span key={index} className={styles.keywordTag}>
              {keyword}
            </span>
          ))}
        </div>
      </div>
    );
  };

  // 渲染深度分析Tab
  const renderDeepAnalysisTab = () => {
    if (!pdfText) {
      return (
        <div className={styles.empty}>
          <p>上传PDF后可进行深度分析</p>
        </div>
      );
    }

    const hasAnalysis = deepAnalysis && (deepAnalysis.dimensions.length > 0 || deepAnalysis.knowledgePoints.length > 0);

    return (
      <div className={styles.tabContent} ref={containerRef}>
        {!hasAnalysis && !isDeepAnalyzing && (
          <div className={styles.empty}>
            <p className={styles.emptyIcon}>📭</p>
            <p className={styles.emptyTitle}>尚未生成深度分析</p>
            <p className={styles.emptyHint}>点击上方「深度分析」按钮开始分析</p>
          </div>
        )}
        
        {/* 6维度卡片 */}
        {deepAnalysis?.dimensions.map((dim, index) => (
          <div 
            key={dim.dimension} 
            className={`${styles.dimensionCard} ${expandedDimensions.has(dim.dimension) ? styles.expanded : ''}`}
            style={{ animationDelay: `${index * 0.1}s` }}
          >
            <div 
              className={styles.dimensionHeader}
              onClick={() => toggleDimension(dim.dimension)}
            >
              <span className={styles.dimensionIcon}>{dimensionIcons[dim.dimension] || '📄'}</span>
              <span className={styles.dimensionTitle}>{dim.title}</span>
              <span className={styles.expandIcon}>
                {expandedDimensions.has(dim.dimension) ? '▼' : '▶'}
              </span>
            </div>
            {expandedDimensions.has(dim.dimension) && (
              <div className={styles.dimensionContent}>
                <MarkdownContent content={dim.content} />
              </div>
            )}
          </div>
        ))}

        {/* 知识点区域 */}
        {deepAnalysis?.knowledgePoints.length > 0 && (
          <div className={styles.knowledgeSection}>
            <h4 className={styles.knowledgeSectionTitle}>
              <span>{dimensionIcons.knowledge_point}</span>
              核心知识点
            </h4>
            {deepAnalysis.knowledgePoints.map((kp, index) => (
              <div 
                key={index} 
                className={`${styles.knowledgeCard} ${expandedKnowledgePoints.has(index) ? styles.expanded : ''}`}
                style={{ animationDelay: `${(deepAnalysis.dimensions.length + index) * 0.1}s` }}
              >
                <div 
                  className={styles.knowledgeHeader}
                  onClick={() => toggleKnowledgePoint(index)}
                >
                  <span className={styles.knowledgeIcon}>🎯</span>
                  <span className={styles.knowledgeTitle}>{kp.title || `知识点 ${index + 1}`}</span>
                  <span className={styles.expandIcon}>
                    {expandedKnowledgePoints.has(index) ? '▼' : '▶'}
                  </span>
                </div>
                {expandedKnowledgePoints.has(index) && (
                  <div className={styles.knowledgeContent}>
                    <MarkdownContent content={kp.content} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* 导出按钮 */}
        {hasAnalysis && (
          <button className={styles.exportBtn} onClick={handleExportReport}>
            <span>📥</span>
            导出分析报告
          </button>
        )}

        {isDeepAnalyzing && (
          <div className={styles.loading}>
            <div className={styles.spinner}></div>
            <span>正在进行深度分析...</span>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className={styles.container}>
      {/* Tab 切换 */}
      <div className={styles.tabBar}>
        <button 
          className={`${styles.tabBtn} ${activeTab === 'overview' ? styles.active : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          章节概览
          {isAnalyzing && <span className={styles.tabIndicator}>●</span>}
        </button>
        <button 
          className={`${styles.tabBtn} ${activeTab === 'deep' ? styles.active : ''}`}
          onClick={() => setActiveTab('deep')}
        >
          深度分析
          {isDeepAnalyzing && <span className={styles.tabIndicator}>●</span>}
        </button>
        <button 
          className={`${styles.tabBtn} ${activeTab === 'keywords' ? styles.active : ''}`}
          onClick={() => setActiveTab('keywords')}
        >
          关键词
          {keywords.length > 0 && <span className={styles.tabBadge}>{keywords.length}</span>}
        </button>
      </div>

      {/* Tab 内容 */}
      {activeTab === 'overview' ? renderOverviewTab() : activeTab === 'deep' ? renderDeepAnalysisTab() : renderKeywordsTab()}
    </div>
  );
}

export default ExplanationPanel;

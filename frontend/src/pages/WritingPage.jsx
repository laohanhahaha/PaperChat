import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import MarkdownContent from '../utils/MarkdownRenderer';
import useWritingStore from '../stores/writingStore';
import usePaperStore from '../stores/paperStore';
import styles from './WritingPage.module.css';

// 解析对比分析的 JSON 流
const parseCompareChunks = (chunks) => {
  const fullText = chunks.join('');
  const dimensions = [];
  
  // 按行分割，尝试解析每行 JSON
  const lines = fullText.split('\n').filter(line => line.trim());
  
  for (const line of lines) {
    try {
      // 尝试找到 JSON 对象
      const jsonMatch = line.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        const data = JSON.parse(jsonMatch[0]);
        if (data.dimension && data.title && data.content) {
          dimensions.push(data);
        }
      }
    } catch {
      // 忽略解析失败的行
    }
  }
  
  return dimensions;
};

// 大纲生成 Tab
function OutlineTab() {
  const [topic, setTopic] = useState('');
  const [requirements, setRequirements] = useState('');
  const [selectedPapers, setSelectedPapers] = useState([]);
  const [output, setOutput] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  
  const { papers, fetchPapers } = usePaperStore();
  const { 
    isGenerating, 
    generateOutline 
  } = useWritingStore();
  
  useEffect(() => {
    fetchPapers();
  }, [fetchPapers]);
  
  const handleGenerate = async () => {
    if (!topic.trim()) return;
    setOutput('');
    try {
      await generateOutline(topic, selectedPapers, requirements);
    } catch (error) {
      console.error('生成大纲失败:', error);
    }
  };
  
  const handleExport = () => {
    const blob = new Blob([output], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `论文大纲_${topic.slice(0, 20)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };
  
  const togglePaperSelection = (paperId) => {
    setSelectedPapers(prev => 
      prev.includes(paperId) 
        ? prev.filter(id => id !== paperId)
        : [...prev, paperId]
    );
  };
  
  return (
    <div className={styles.tabContent}>
      <div className={styles.inputSection}>
        <div className={styles.formGroup}>
          <label>研究主题</label>
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="请输入研究主题，例如：深度学习在医学影像诊断中的应用"
            className={styles.textInput}
          />
        </div>
        
        <div className={styles.formGroup}>
          <label>额外要求（可选）</label>
          <textarea
            value={requirements}
            onChange={(e) => setRequirements(e.target.value)}
            placeholder="例如：重点关注卷积神经网络，包含实验设计部分..."
            className={styles.textarea}
            rows={3}
          />
        </div>
        
        <div className={styles.formGroup}>
          <label>选择参考论文（可选）</label>
          <div className={styles.paperSelector}>
            {papers.length === 0 ? (
              <p className={styles.emptyText}>暂无论文，请先上传论文</p>
            ) : (
              papers.map(paper => (
                <label key={paper.id} className={styles.paperCheckbox}>
                  <input
                    type="checkbox"
                    checked={selectedPapers.includes(paper.id)}
                    onChange={() => togglePaperSelection(paper.id)}
                  />
                  <span className={styles.paperTitle}>{paper.title}</span>
                </label>
              ))
            )}
          </div>
        </div>
        
        <button
          onClick={handleGenerate}
          disabled={isGenerating || !topic.trim()}
          className={styles.generateBtn}
        >
          {isGenerating ? '生成中...' : '生成大纲'}
        </button>
      </div>
      
      <div className={styles.outputSection}>
        <div className={styles.outputHeader}>
          <h3>生成结果</h3>
          <div className={styles.outputActions}>
            <button
              onClick={() => setIsEditing(!isEditing)}
              className={styles.actionBtn}
              disabled={!output}
            >
              {isEditing ? '预览' : '编辑'}
            </button>
            <button
              onClick={handleExport}
              className={styles.actionBtn}
              disabled={!output}
            >
              导出
            </button>
          </div>
        </div>
        
        {isEditing ? (
          <textarea
            value={output}
            onChange={(e) => setOutput(e.target.value)}
            className={styles.outputEditor}
            placeholder="大纲将在这里显示..."
          />
        ) : (
          <div className={styles.outputPreview}>
            {output ? (
              <div className={styles.markdownContent}>
                <ReactMarkdown>{output}</ReactMarkdown>
              </div>
            ) : (
              <p className={styles.placeholder}>大纲将在这里显示...</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// 段落生成 Tab
function DraftTab() {
  const [outlineSection, setOutlineSection] = useState('');
  const [context, setContext] = useState('');
  const [style, setStyle] = useState('academic');
  const [output, setOutput] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  
  const { isGenerating, generateDraft } = useWritingStore();
  
  const handleGenerate = async () => {
    if (!outlineSection.trim()) return;
    setOutput('');
    try {
      await generateDraft(outlineSection, context, style);
    } catch (error) {
      console.error('生成段落失败:', error);
    }
  };
  
  const styleOptions = [
    { value: 'academic', label: '学术风格' },
    { value: 'formal', label: '正式风格' },
    { value: 'concise', label: '简洁风格' },
  ];
  
  return (
    <div className={styles.tabContent}>
      <div className={styles.inputSection}>
        <div className={styles.formGroup}>
          <label>大纲节点</label>
          <textarea
            value={outlineSection}
            onChange={(e) => setOutlineSection(e.target.value)}
            placeholder="请输入大纲节点内容，例如：3.2 卷积神经网络的基本原理"
            className={styles.textarea}
            rows={3}
          />
        </div>
        
        <div className={styles.formGroup}>
          <label>参考内容（可选）</label>
          <textarea
            value={context}
            onChange={(e) => setContext(e.target.value)}
            placeholder="粘贴相关参考内容，或从论文中复制相关段落..."
            className={styles.textarea}
            rows={5}
          />
        </div>
        
        <div className={styles.formGroup}>
          <label>写作风格</label>
          <select
            value={style}
            onChange={(e) => setStyle(e.target.value)}
            className={styles.select}
          >
            {styleOptions.map(opt => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
        
        <button
          onClick={handleGenerate}
          disabled={isGenerating || !outlineSection.trim()}
          className={styles.generateBtn}
        >
          {isGenerating ? '生成中...' : '生成段落'}
        </button>
      </div>
      
      <div className={styles.outputSection}>
        <div className={styles.outputHeader}>
          <h3>生成结果</h3>
          <button
            onClick={() => setIsEditing(!isEditing)}
            className={styles.actionBtn}
            disabled={!output}
          >
            {isEditing ? '预览' : '编辑'}
          </button>
        </div>
        
        {isEditing ? (
          <textarea
            value={output}
            onChange={(e) => setOutput(e.target.value)}
            className={styles.outputEditor}
            placeholder="生成的段落将在这里显示..."
          />
        ) : (
          <div className={styles.outputPreview}>
            {output ? (
              <div className={styles.paragraphContent}>
                <ReactMarkdown>{output}</ReactMarkdown>
              </div>
            ) : (
              <p className={styles.placeholder}>生成的段落将在这里显示...</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// 学术润色 Tab
function PolishTab() {
  const [inputText, setInputText] = useState('');
  const [polishType, setPolishType] = useState('academic');
  const [output, setOutput] = useState('');
  const [showCompare, setShowCompare] = useState(false);
  
  const { isGenerating, polishText } = useWritingStore();
  
  const handlePolish = async () => {
    if (!inputText.trim()) return;
    setOutput('');
    setShowCompare(false);
    try {
      await polishText(inputText, polishType);
    } catch (error) {
      console.error('润色失败:', error);
    }
  };
  
  const polishTypes = [
    { value: 'academic', label: '学术表达', desc: '提升学术性，使用更专业的术语和句式' },
    { value: 'grammar', label: '语法修正', desc: '修正语法错误、标点问题' },
    { value: 'fluency', label: '流畅性', desc: '优化句子流畅度，改善可读性' },
    { value: 'concise', label: '精简表达', desc: '删除冗余内容，使表达更简洁' },
  ];
  
  return (
    <div className={styles.tabContent}>
      <div className={styles.inputSection}>
        <div className={styles.formGroup}>
          <label>待润色文本</label>
          <textarea
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="请输入需要润色的学术文本..."
            className={styles.textarea}
            rows={8}
          />
        </div>
        
        <div className={styles.formGroup}>
          <label>润色类型</label>
          <div className={styles.radioGroup}>
            {polishTypes.map(type => (
              <label key={type.value} className={styles.radioLabel}>
                <input
                  type="radio"
                  value={type.value}
                  checked={polishType === type.value}
                  onChange={(e) => setPolishType(e.target.value)}
                />
                <span className={styles.radioText}>
                  <strong>{type.label}</strong>
                  <small>{type.desc}</small>
                </span>
              </label>
            ))}
          </div>
        </div>
        
        <button
          onClick={handlePolish}
          disabled={isGenerating || !inputText.trim()}
          className={styles.generateBtn}
        >
          {isGenerating ? '润色中...' : '开始润色'}
        </button>
      </div>
      
      <div className={styles.outputSection}>
        <div className={styles.outputHeader}>
          <h3>润色结果</h3>
          {output && (
            <button
              onClick={() => setShowCompare(!showCompare)}
              className={styles.actionBtn}
            >
              {showCompare ? '隐藏对比' : '对比视图'}
            </button>
          )}
        </div>
        
        {showCompare ? (
          <div className={styles.compareView}>
            <div className={styles.compareColumn}>
              <h4>原文</h4>
              <div className={styles.compareContent}>{inputText}</div>
            </div>
            <div className={styles.compareColumn}>
              <h4>润色后</h4>
              <div className={styles.compareContent}>{output}</div>
            </div>
          </div>
        ) : (
          <div className={styles.outputPreview}>
            {output ? (
              <div className={styles.polishedContent}>
                <ReactMarkdown>{output}</ReactMarkdown>
              </div>
            ) : (
              <p className={styles.placeholder}>润色结果将在这里显示...</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// 引用格式 Tab
function CitationTab() {
  const [selectedPapers, setSelectedPapers] = useState([]);
  const [format, setFormat] = useState('apa');
  const [citations, setCitations] = useState([]);
  const [copiedIndex, setCopiedIndex] = useState(null);
  
  const { papers, fetchPapers } = usePaperStore();
  const { isGenerating, generateCitations } = useWritingStore();
  
  useEffect(() => {
    fetchPapers();
  }, [fetchPapers]);
  
  const handleGenerate = async () => {
    if (selectedPapers.length === 0) return;
    try {
      const result = await generateCitations(selectedPapers, format);
      setCitations(result);
    } catch (error) {
      console.error('生成引用失败:', error);
    }
  };
  
  const handleCopy = (text, index) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };
  
  const handleCopyAll = () => {
    const allCitations = citations
      .filter(c => c.citation)
      .map(c => c.citation)
      .join('\n');
    navigator.clipboard.writeText(allCitations);
  };
  
  const togglePaperSelection = (paperId) => {
    setSelectedPapers(prev => 
      prev.includes(paperId) 
        ? prev.filter(id => id !== paperId)
        : [...prev, paperId]
    );
  };
  
  const formatOptions = [
    { value: 'apa', label: 'APA', desc: '美国心理学会格式' },
    { value: 'mla', label: 'MLA', desc: '现代语言协会格式' },
    { value: 'chicago', label: 'Chicago', desc: '芝加哥格式' },
    { value: 'gbt7714', label: 'GB/T 7714', desc: '中国国家标准' },
  ];
  
  return (
    <div className={styles.tabContent}>
      <div className={styles.inputSection}>
        <div className={styles.formGroup}>
          <label>选择论文</label>
          <div className={styles.paperSelector}>
            {papers.length === 0 ? (
              <p className={styles.emptyText}>暂无论文，请先上传论文</p>
            ) : (
              papers.map(paper => (
                <label key={paper.id} className={styles.paperCheckbox}>
                  <input
                    type="checkbox"
                    checked={selectedPapers.includes(paper.id)}
                    onChange={() => togglePaperSelection(paper.id)}
                  />
                  <span className={styles.paperTitle}>{paper.title}</span>
                </label>
              ))
            )}
          </div>
        </div>
        
        <div className={styles.formGroup}>
          <label>引用格式</label>
          <div className={styles.formatOptions}>
            {formatOptions.map(opt => (
              <label key={opt.value} className={styles.formatRadio}>
                <input
                  type="radio"
                  value={opt.value}
                  checked={format === opt.value}
                  onChange={(e) => setFormat(e.target.value)}
                />
                <span className={styles.formatLabel}>
                  <strong>{opt.label}</strong>
                  <small>{opt.desc}</small>
                </span>
              </label>
            ))}
          </div>
        </div>
        
        <button
          onClick={handleGenerate}
          disabled={isGenerating || selectedPapers.length === 0}
          className={styles.generateBtn}
        >
          {isGenerating ? '生成中...' : '生成引用'}
        </button>
      </div>
      
      <div className={styles.outputSection}>
        <div className={styles.outputHeader}>
          <h3>引用列表</h3>
          {citations.length > 0 && (
            <button onClick={handleCopyAll} className={styles.actionBtn}>
              一键复制全部
            </button>
          )}
        </div>
        
        <div className={styles.citationList}>
          {citations.length === 0 ? (
            <p className={styles.placeholder}>引用将在这里显示...</p>
          ) : (
            citations.map((item, index) => (
              <div key={item.paper_id} className={styles.citationItem}>
                <div className={styles.citationText}>
                  {item.citation ? (
                    <p>{item.citation}</p>
                  ) : (
                    <p className={styles.errorText}>错误: {item.error}</p>
                  )}
                </div>
                {item.citation && (
                  <button
                    onClick={() => handleCopy(item.citation, index)}
                    className={styles.copyBtn}
                  >
                    {copiedIndex === index ? '已复制!' : '复制'}
                  </button>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

// 文章对比 Tab
function CompareTab() {
  const [selectedPaperIds, setSelectedPaperIds] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [compareChunks, setCompareChunks] = useState([]);
  const [compareDimensions, setCompareDimensions] = useState([]);
  
  const { papers, fetchPapers } = usePaperStore();
  const abortControllerRef = useRef(null);
  
  useEffect(() => {
    if (papers.length === 0) {
      fetchPapers({ page: 1, page_size: 100 });
    }
  }, [fetchPapers, papers.length]);
  
  // 清理
  useEffect(() => {
    const controller = abortControllerRef.current;
    return () => {
      if (controller) {
        controller.abort();
      }
    };
  }, []);
  
  // 解析维度
  useEffect(() => {
    if (compareChunks.length > 0) {
      const dimensions = parseCompareChunks(compareChunks);
      setCompareDimensions(dimensions);
    }
  }, [compareChunks]);
  
  const togglePaperSelection = (paperId) => {
    setSelectedPaperIds(prev => 
      prev.includes(paperId) 
        ? prev.filter(id => id !== paperId)
        : prev.length < 10 ? [...prev, paperId] : prev
    );
  };
  
  const handleRemovePaper = (paperId) => {
    setSelectedPaperIds(prev => prev.filter(id => id !== paperId));
  };
  
  const handleCompare = async () => {
    if (selectedPaperIds.length < 2) {
      setError('请至少选择 2 篇论文');
      return;
    }

    setIsLoading(true);
    setError(null);
    setCompareChunks([]);
    setCompareDimensions([]);

    try {
      console.log('[CompareTab] 发起对比分析请求, paper_ids:', selectedPaperIds);

      const headers = { 'Content-Type': 'application/json' };
      // 单用户模式，不需要 Authorization header

      const response = await fetch('/api/v1/analysis/compare', {
        method: 'POST',
        headers,
        body: JSON.stringify({ paper_ids: selectedPaperIds }),
      });

      console.log('[CompareTab] 响应状态:', response.status, response.ok);

      if (!response.ok) {
        let errorMsg = `请求失败: ${response.status}`;
        try {
          const errorData = await response.json();
          errorMsg = errorData.detail || errorMsg;
        } catch { /* ignore */ }
        throw new Error(errorMsg);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let hasReceivedData = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const event of events) {
          const trimmed = event.trim();
          if (!trimmed.startsWith('data: ')) continue;

          try {
            const data = JSON.parse(trimmed.slice(6));
            if (data.chunk) {
              hasReceivedData = true;
              setCompareChunks(prev => [...prev, data.chunk]);
            } else if (data.done) {
              // 流结束
            } else if (data.error) {
              setError(data.error);
              setIsLoading(false);
              return;
            }
          } catch {
            console.warn('[CompareTab] SSE 解析失败:', trimmed);
          }
        }
      }

      // 处理 buffer 中残留数据
      if (buffer.trim().startsWith('data: ')) {
        try {
          const data = JSON.parse(buffer.trim().slice(6));
          if (data.chunk) {
            hasReceivedData = true;
            setCompareChunks(prev => [...prev, data.chunk]);
          } else if (data.done) {
            // 流结束
          } else if (data.error) {
            setError(data.error);
          }
        } catch { /* ignore */ }
      }

      if (!hasReceivedData) {
        setError('分析未返回数据，请检查后端服务和 API Key 配置是否正确');
      }

      setIsLoading(false);
    } catch (err) {
      console.error('[CompareTab] 分析失败:', err);
      setError(err.message || '分析失败，请重试');
      setIsLoading(false);
    }
  };
  
  const handleExport = () => {
    const selectedPapers = papers.filter(p => selectedPaperIds.includes(p.id));
    let content = `# 论文对比分析\n\n`;
    content += `## 选中的论文\n\n`;
    selectedPapers.forEach((p, i) => {
      content += `${i + 1}. ${p.title}\n`;
    });
    content += `\n---\n\n`;
    
    compareDimensions.forEach(dim => {
      content += `## ${dim.title}\n\n${dim.content}\n\n`;
    });
    
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `论文对比分析_${new Date().toISOString().split('T')[0]}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };
  
  const selectedPapers = papers.filter(p => selectedPaperIds.includes(p.id));
  
  return (
    <div className={styles.tabContent}>
      <div className={styles.inputSection}>
        <div className={`${styles.formGroup} ${styles.paperSelectGroup}`}>
          <label>选择论文进行对比（2-10 篇）</label>
          <div className={styles.selectedCount}>
            已选择 {selectedPaperIds.length} 篇论文
            {selectedPaperIds.length < 2 && <span style={{ color: '#e53e3e' }}>（至少需要 2 篇）</span>}
          </div>
          
          {selectedPaperIds.length > 0 && (
            <div className={styles.selectedPapersBar}>
              {selectedPapers.map(paper => (
                <div key={paper.id} className={styles.selectedPaperTag}>
                  <span>{paper.title.slice(0, 20)}...</span>
                  <button 
                    className={styles.removeTagBtn}
                    onClick={() => handleRemovePaper(paper.id)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
          
          <button
            onClick={handleCompare}
            disabled={isLoading || selectedPaperIds.length < 2}
            className={styles.generateBtn}
          >
            {isLoading ? '分析中...' : '开始对比'}
          </button>
          
          <div className={styles.paperSelectorLarge}>
            {papers.length === 0 ? (
              <p className={styles.emptyText}>暂无论文，请先上传论文</p>
            ) : (
              papers.map(paper => (
                <label key={paper.id} className={styles.paperCheckboxLarge}>
                  <input
                    type="checkbox"
                    checked={selectedPaperIds.includes(paper.id)}
                    onChange={() => togglePaperSelection(paper.id)}
                    disabled={!selectedPaperIds.includes(paper.id) && selectedPaperIds.length >= 10}
                  />
                  <div className={styles.paperInfo}>
                    <span className={styles.paperTitleLarge}>{paper.title}</span>
                    {paper.authors && <span className={styles.paperAuthor}>{paper.authors}</span>}
                  </div>
                </label>
              ))
            )}
          </div>
        </div>
      </div>
      
      <div className={styles.outputSectionFull}>
        <div className={styles.outputHeaderFull}>
          <h3>对比分析结果</h3>
          <button
            onClick={handleExport}
            className={styles.actionBtn}
            disabled={isLoading || compareDimensions.length === 0}
          >
            导出 Markdown
          </button>
        </div>
        
        {error && (
          <div className={styles.errorBanner}>
            {error}
            <button onClick={() => setError(null)} className={styles.closeErrorBtn}>×</button>
          </div>
        )}
        
        <div style={{ flex: 1, overflow: 'auto' }}>
          {isLoading && compareDimensions.length === 0 ? (
            <div className={styles.loadingContainer}>
              <div className={styles.spinner}></div>
              <p>正在分析论文...</p>
            </div>
          ) : compareDimensions.length > 0 ? (
            <div className={styles.dimensionsGrid}>
              {compareDimensions.map((dim, index) => (
                <div key={dim.dimension || index} className={styles.dimensionCard}>
                  <h4 className={styles.dimensionTitle}>{dim.title}</h4>
                  <div className={styles.dimensionContent}>
                    <MarkdownContent content={dim.content} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className={styles.outputPreview}>
              <p className={styles.placeholder}>选择论文后点击"开始对比"进行分析</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// 文献综述 Tab
function ReviewTab() {
  const [selectedPaperIds, setSelectedPaperIds] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [reviewContent, setReviewContent] = useState('');
  
  const { papers, fetchPapers } = usePaperStore();
  const abortControllerRef = useRef(null);
  
  useEffect(() => {
    if (papers.length === 0) {
      fetchPapers({ page: 1, page_size: 100 });
    }
  }, [fetchPapers, papers.length]);
  
  // 清理
  useEffect(() => {
    const controller = abortControllerRef.current;
    return () => {
      if (controller) {
        controller.abort();
      }
    };
  }, []);
  
  const togglePaperSelection = (paperId) => {
    setSelectedPaperIds(prev => 
      prev.includes(paperId) 
        ? prev.filter(id => id !== paperId)
        : prev.length < 10 ? [...prev, paperId] : prev
    );
  };
  
  const handleRemovePaper = (paperId) => {
    setSelectedPaperIds(prev => prev.filter(id => id !== paperId));
  };
  
  const handleGenerateReview = async () => {
    if (selectedPaperIds.length < 2) {
      setError('请至少选择 2 篇论文');
      return;
    }

    setIsLoading(true);
    setError(null);
    setReviewContent('');

    try {
      console.log('[ReviewTab] 发起文献综述请求, paper_ids:', selectedPaperIds);

      const headers = { 'Content-Type': 'application/json' };
      // 单用户模式，不需要 Authorization header

      const response = await fetch('/api/v1/analysis/review', {
        method: 'POST',
        headers,
        body: JSON.stringify({ paper_ids: selectedPaperIds }),
      });

      console.log('[ReviewTab] 响应状态:', response.status, response.ok);

      if (!response.ok) {
        let errorMsg = `请求失败: ${response.status}`;
        try {
          const errorData = await response.json();
          errorMsg = errorData.detail || errorMsg;
        } catch { /* ignore */ }
        throw new Error(errorMsg);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let hasReceivedData = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const event of events) {
          const trimmed = event.trim();
          if (!trimmed.startsWith('data: ')) continue;

          try {
            const data = JSON.parse(trimmed.slice(6));
            if (data.chunk) {
              hasReceivedData = true;
              setReviewContent(prev => prev + data.chunk);
            } else if (data.done) {
              // 流结束
            } else if (data.error) {
              setError(data.error);
              setIsLoading(false);
              return;
            }
          } catch {
            console.warn('[ReviewTab] SSE 解析失败:', trimmed);
          }
        }
      }

      // 处理 buffer 中残留数据
      if (buffer.trim().startsWith('data: ')) {
        try {
          const data = JSON.parse(buffer.trim().slice(6));
          if (data.chunk) {
            hasReceivedData = true;
            setReviewContent(prev => prev + data.chunk);
          } else if (data.done) {
            // 流结束
          } else if (data.error) {
            setError(data.error);
          }
        } catch { /* ignore */ }
      }

      if (!hasReceivedData) {
        setError('分析未返回数据，请检查后端服务和 API Key 配置是否正确');
      }

      setIsLoading(false);
    } catch (err) {
      console.error('[ReviewTab] 生成综述失败:', err);
      setError(err.message || '生成综述失败，请重试');
      setIsLoading(false);
    }
  };
  
  const handleExport = () => {
    const blob = new Blob([reviewContent], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `文献综述_${new Date().toISOString().split('T')[0]}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };
  
  const selectedPapers = papers.filter(p => selectedPaperIds.includes(p.id));
  
  return (
    <div className={styles.tabContent}>
      <div className={styles.inputSection}>
        <div className={`${styles.formGroup} ${styles.paperSelectGroup}`}>
          <label>选择论文生成综述（2-10 篇）</label>
          <div className={styles.selectedCount}>
            已选择 {selectedPaperIds.length} 篇论文
            {selectedPaperIds.length < 2 && <span style={{ color: '#e53e3e' }}>（至少需要 2 篇）</span>}
          </div>
          
          {selectedPaperIds.length > 0 && (
            <div className={styles.selectedPapersBar}>
              {selectedPapers.map(paper => (
                <div key={paper.id} className={styles.selectedPaperTag}>
                  <span>{paper.title.slice(0, 20)}...</span>
                  <button 
                    className={styles.removeTagBtn}
                    onClick={() => handleRemovePaper(paper.id)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
          
          <button
            onClick={handleGenerateReview}
            disabled={isLoading || selectedPaperIds.length < 2}
            className={styles.generateBtn}
          >
            {isLoading ? '生成中...' : '生成综述'}
          </button>
          
          <div className={styles.paperSelectorLarge}>
            {papers.length === 0 ? (
              <p className={styles.emptyText}>暂无论文，请先上传论文</p>
            ) : (
              papers.map(paper => (
                <label key={paper.id} className={styles.paperCheckboxLarge}>
                  <input
                    type="checkbox"
                    checked={selectedPaperIds.includes(paper.id)}
                    onChange={() => togglePaperSelection(paper.id)}
                    disabled={!selectedPaperIds.includes(paper.id) && selectedPaperIds.length >= 10}
                  />
                  <div className={styles.paperInfo}>
                    <span className={styles.paperTitleLarge}>{paper.title}</span>
                    {paper.authors && <span className={styles.paperAuthor}>{paper.authors}</span>}
                  </div>
                </label>
              ))
            )}
          </div>
        </div>
      </div>
      
      <div className={styles.outputSectionFull}>
        <div className={styles.outputHeaderFull}>
          <h3>文献综述</h3>
          <button
            onClick={handleExport}
            className={styles.actionBtn}
            disabled={isLoading || !reviewContent}
          >
            导出 Markdown
          </button>
        </div>
        
        {error && (
          <div className={styles.errorBanner}>
            {error}
            <button onClick={() => setError(null)} className={styles.closeErrorBtn}>×</button>
          </div>
        )}
        
        <div style={{ flex: 1, overflow: 'auto' }}>
          {isLoading && !reviewContent ? (
            <div className={styles.loadingContainer}>
              <div className={styles.spinner}></div>
              <p>正在生成文献综述...</p>
            </div>
          ) : reviewContent ? (
            <div className={styles.reviewContent}>
              <MarkdownContent content={reviewContent} />
            </div>
          ) : (
            <div className={styles.outputPreview}>
              <p className={styles.placeholder}>选择论文后点击"生成综述"</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// 主页面组件
function WritingPage() {
  const [searchParams] = useSearchParams();
  const { reset } = useWritingStore();
  
  // 从 URL 参数获取初始 Tab
  const getInitialTab = () => {
    const tabParam = searchParams.get('tab');
    const validTabs = ['outline', 'draft', 'polish', 'citation', 'compare', 'review'];
    return validTabs.includes(tabParam) ? tabParam : 'outline';
  };
  
  const [activeTab, setActiveTab] = useState(getInitialTab);
  
  // 切换 Tab 时重置状态
  const handleTabChange = useCallback((tab) => {
    reset();
    setActiveTab(tab);
  }, [reset]);
  
  const tabs = [
    { id: 'outline', label: '大纲生成', icon: '📝' },
    { id: 'draft', label: '段落生成', icon: '📄' },
    { id: 'polish', label: '学术润色', icon: '✨' },
    { id: 'citation', label: '引用格式', icon: '📚' },
    { id: 'compare', label: '文章对比', icon: '📊' },
    { id: 'review', label: '文献综述', icon: '📑' },
  ];
  
  return (
    <div className={styles.writingPage}>
      <header className={styles.header}>
        <h1>学术写作辅助</h1>
        <p className={styles.subtitle}>大纲生成 / 段落初稿 / 学术润色 / 引用格式</p>
      </header>
      
      <div className={styles.container}>
        <aside className={styles.sidebar}>
          <nav className={styles.tabNav}>
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                className={`${styles.tabBtn} ${activeTab === tab.id ? styles.active : ''}`}
              >
                <span className={styles.tabIcon}>{tab.icon}</span>
                <span className={styles.tabLabel}>{tab.label}</span>
              </button>
            ))}
          </nav>
          
          <div className={styles.sidebarInfo}>
            <h4>使用提示</h4>
            <ul>
              <li>大纲生成支持参考已上传论文</li>
              <li>段落生成可粘贴参考内容</li>
              <li>润色支持 4 种优化类型</li>
              <li>引用支持 4 种标准格式</li>
              <li>文章对比支持维度化分析</li>
              <li>文献综述自动整合多篇论文</li>
            </ul>
          </div>
        </aside>
        
        <main className={styles.mainContent}>
          {activeTab === 'outline' && <OutlineTab />}
          {activeTab === 'draft' && <DraftTab />}
          {activeTab === 'polish' && <PolishTab />}
          {activeTab === 'citation' && <CitationTab />}
          {activeTab === 'compare' && <CompareTab />}
          {activeTab === 'review' && <ReviewTab />}
        </main>
      </div>
    </div>
  );
}

export default WritingPage;

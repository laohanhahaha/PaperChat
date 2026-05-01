import React, { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import MarkdownContent from '../../utils/MarkdownRenderer';
import { INTENT_LABELS } from '../../utils/chatConstants';
import styles from './ToolResultCard.module.css';

/**
 * 解析 tool_result 的 content 字段
 * content 可能是 JSON 字符串或纯文本
 */
function parseContent(content) {
  if (!content) return null;
  if (typeof content === 'object') return content;
  try {
    return JSON.parse(content);
  } catch {
    return null;
  }
}

/* ===== Writing 类型卡片 (literature_review, polish_text) ===== */
function WritingCard({ tool, content }) {
  const [copied, setCopied] = useState(false);
  const parsed = parseContent(content);
  const text = parsed
    ? (typeof parsed.text === 'string' ? parsed.text : (typeof parsed.content === 'string' ? parsed.content : null))
    : (typeof content === 'string' ? content : null);
  const label = INTENT_LABELS[tool] || tool;

  const handleCopy = useCallback(() => {
    const copyText = text || (typeof content === 'string' ? content : JSON.stringify(content));
    navigator.clipboard.writeText(copyText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [text, content]);

  if (!text && !content) return null;

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.cardTitle}>{label}</span>
        <button className={styles.copyBtn} onClick={handleCopy}>
          {copied ? '✓ 已复制' : '复制'}
        </button>
      </div>
      <div className={styles.writingBody}>
        {text ? (
          <MarkdownContent content={text} />
        ) : (
          typeof content === 'string' ? <MarkdownContent content={content} /> : JSON.stringify(content)
        )}
      </div>
    </div>
  );
}

/* ===== Citation 类型卡片 (cite_paper) ===== */
function CitationCard({ tool, content }) {
  const [copied, setCopied] = useState(false);
  const parsed = parseContent(content);
  const citation = parsed
    ? (typeof parsed.citation === 'string' ? parsed.citation : (typeof parsed.text === 'string' ? parsed.text : null))
    : (typeof content === 'string' ? content : null);
  const label = INTENT_LABELS[tool] || tool;

  const handleCopy = useCallback(() => {
    const copyText = citation || (typeof content === 'string' ? content : JSON.stringify(content));
    navigator.clipboard.writeText(copyText).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [citation, content]);

  if (!citation && !content) return null;

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.cardTitle}>{label}</span>
        <button className={styles.copyBtn} onClick={handleCopy}>
          {copied ? '✓ 已复制' : '复制引用'}
        </button>
      </div>
      <div className={styles.citationBody}>
        {citation || content}
      </div>
    </div>
  );
}

/* ===== Knowledge 类型卡片 (save_card, search_cards) ===== */
function KnowledgeCard({ tool, content }) {
  const navigate = useNavigate();
  const parsed = parseContent(content);

  // save_card: 保存成功的确认卡片
  if (tool === 'save_card') {
    const title = parsed?.title || (typeof content === 'string' ? content : '知识卡片');
    return (
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <span className={styles.cardTitle}>{INTENT_LABELS[tool] || tool}</span>
        </div>
        <div className={styles.confirmBody}>
          <span className={styles.checkIcon}>✓</span>
          <span className={styles.confirmText}>已保存: {title}</span>
          <button
            className={styles.actionBtn}
            onClick={() => navigate('/knowledge')}
            style={{ marginLeft: 'auto' }}
          >
            查看知识库
          </button>
        </div>
      </div>
    );
  }

  // search_cards: 知识卡片列表
  const cards = Array.isArray(parsed) ? parsed
    : (parsed?.cards ? parsed.cards : null);

  if (!cards || !Array.isArray(cards)) {
    // 降级为纯文本显示
    return (
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <span className={styles.cardTitle}>{INTENT_LABELS[tool] || tool}</span>
        </div>
        <div className={styles.writingBody}>
          {typeof content === 'string' ? content : JSON.stringify(content)}
        </div>
      </div>
    );
  }

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.cardTitle}>{INTENT_LABELS[tool] || tool}</span>
        <div className={styles.cardHeaderRight}>
          <span className={styles.cardCount}>{cards.length} 条结果</span>
          <button
            className={styles.actionBtn}
            onClick={() => navigate('/knowledge')}
          >
            查看知识库
          </button>
        </div>
      </div>
      <div className={styles.cardList}>
        {cards.map((item, idx) => (
          <div key={idx} className={styles.knowledgeItem}>
            <div className={styles.knowledgeTitle}>{item.title || '无标题'}</div>
            {item.summary && (
              <div className={styles.knowledgeSummary}>{item.summary}</div>
            )}
            {item.content && !item.summary && (
              <div className={styles.knowledgeSummary}>
                {item.content.length > 200 ? item.content.slice(0, 200) + '...' : item.content}
              </div>
            )}
            {item.tags && Array.isArray(item.tags) && item.tags.length > 0 && (
              <div className={styles.tagList}>
                {item.tags.map((tag, tidx) => (
                  <span key={tidx} className={styles.tag}>{tag}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ===== 来源 Badge 颜色映射 ===== */
const SOURCE_BADGE_COLORS = {
  'arXiv': { bg: 'rgba(178, 34, 34, 0.10)', color: '#B22222', border: 'rgba(178, 34, 34, 0.25)' },
  'Google Scholar': { bg: 'rgba(66, 133, 244, 0.10)', color: '#4285F4', border: 'rgba(66, 133, 244, 0.25)' },
  'Semantic Scholar': { bg: 'rgba(138, 75, 175, 0.10)', color: '#8A4BAF', border: 'rgba(138, 75, 175, 0.25)' },
  'Web': { bg: 'rgba(52, 168, 83, 0.10)', color: '#34A853', border: 'rgba(52, 168, 83, 0.25)' },
};

function SourceBadge({ source }) {
  const colors = SOURCE_BADGE_COLORS[source] || SOURCE_BADGE_COLORS['Web'];
  return (
    <span
      className={styles.sourceBadge}
      style={{ background: colors.bg, color: colors.color, borderColor: colors.border }}
    >
      {source}
    </span>
  );
}

/* ===== 可展开摘要 ===== */
function ExpandableAbstract({ text, limit = 100 }) {
  const [expanded, setExpanded] = useState(false);
  if (!text) return null;
  const needsTruncate = text.length > limit;
  return (
    <div className={styles.paperAbstract}>
      {expanded || !needsTruncate ? text : text.slice(0, limit) + '...'}
      {needsTruncate && (
        <button className={styles.expandBtn} onClick={() => setExpanded(v => !v)}>
          {expanded ? '收起' : '展开'}
        </button>
      )}
    </div>
  );
}

/* ===== Papers 类型卡片 (recent_papers, search_papers) ===== */
function PapersCard({ tool, content }) {
  const navigate = useNavigate();
  const parsed = parseContent(content);

  // loading 状态
  if (parsed && parsed._loading) {
    return (
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <span className={styles.cardTitle}>🔎 正在搜索论文...</span>
          <span className={styles.searchingDots}><span></span><span></span><span></span></span>
        </div>
        <div className={styles.loadingBody}>
          <div className={styles.loadingSkeleton}></div>
          <div className={styles.loadingSkeleton} style={{ width: '70%' }}></div>
          <div className={styles.loadingSkeleton} style={{ width: '50%' }}></div>
        </div>
      </div>
    );
  }

  const source = parsed?.source || 'local'; // 向后兼容：无 source 字段视为 local
  const keywords = parsed?.keywords || [];
  const papers = Array.isArray(parsed) ? parsed
    : (parsed?.papers ? parsed.papers : null);

  // Agent 模式返回的摘要信息（无结构化 papers 数据，仅有文本摘要）
  if (source === 'agent') {
    const summary = parsed?.summary || '';
    const count = parsed?.count || 0;
    return (
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <span className={styles.cardTitle}>
            {count > 0 ? `🔎 Agent 检索到 ${count} 篇论文` : '🔎 Agent 检索完成'}
          </span>
        </div>
        {summary && (
          <div className={styles.writingBody}>
            <span style={{ color: 'var(--color-text-secondary, #666)', fontSize: '13px' }}>{summary}</span>
          </div>
        )}
      </div>
    );
  }

  // 无结果
  if (source === 'none' || (papers && papers.length === 0)) {
    return (
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <span className={styles.cardTitle}>🔎 未找到相关论文</span>
        </div>
        <div className={styles.emptyBody}>
          <span className={styles.emptyIcon}>📭</span>
          <span className={styles.emptyText}>未找到相关论文</span>
          {keywords.length > 0 && (
            <div className={styles.keywordsRow}>
              搜索关键词：{keywords.map((kw, i) => (
                <span key={i} className={styles.keywordTag}>{kw}</span>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  // 降级：无法解析的 papers
  if (!papers || !Array.isArray(papers)) {
    return (
      <div className={styles.card}>
        <div className={styles.cardHeader}>
          <span className={styles.cardTitle}>{INTENT_LABELS[tool] || tool}</span>
        </div>
        <div className={styles.writingBody}>
          {typeof content === 'string' ? content : JSON.stringify(content)}
        </div>
      </div>
    );
  }

  const displayPapers = papers.slice(0, 10);
  const isWeb = source === 'web';

  // 标题文案
  const titleText = isWeb
    ? `🌐 网络搜索 ${papers.length} 篇论文`
    : `📄 本地论文 ${papers.length} 篇`;

  return (
    <div className={`${styles.card} ${isWeb ? styles.webCard : ''}`}>
      <div className={styles.cardHeader}>
        <span className={styles.cardTitle}>{titleText}</span>
        {keywords.length > 0 && (
          <div className={styles.headerKeywords}>
            {keywords.slice(0, 3).map((kw, i) => (
              <span key={i} className={styles.keywordTag}>{kw}</span>
            ))}
          </div>
        )}
      </div>
      <div className={styles.cardList}>
        {displayPapers.map((paper, idx) => (
          <div key={idx} className={`${styles.paperItem} ${isWeb ? styles.webPaperItem : ''}`}>
            <div className={styles.paperItemContent}>
              <div className={styles.paperTitleRow}>
                {isWeb && paper.url ? (
                  <a
                    className={styles.paperTitleLink}
                    href={paper.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    onClick={(e) => { e.stopPropagation(); }}
                  >
                    {paper.title || '无标题'}
                  </a>
                ) : (
                  <div className={styles.paperTitle}>{paper.title || '无标题'}</div>
                )}
                {isWeb && paper.source && <SourceBadge source={paper.source} />}
              </div>
              <div className={styles.paperMeta}>
                {(paper.authors || paper.author) && (
                  <span>{typeof paper.authors === 'string' ? paper.authors : (Array.isArray(paper.authors) ? paper.authors.join(', ') : paper.author)}</span>
                )}
                {paper.year && <span className={styles.paperYear}>{paper.year}</span>}
              </div>
              {isWeb && paper.abstract && <ExpandableAbstract text={paper.abstract} />}
              {!isWeb && paper.created_at && (
                <div className={styles.paperTime}>
                  {new Date(paper.created_at).toLocaleDateString('zh-CN')}
                </div>
              )}
            </div>
            {!isWeb && paper.id && (
              <button
                className={styles.openBtn}
                onClick={() => navigate(`/reader/${paper.id}`)}
                title="打开阅读"
              >
                阅读
              </button>
            )}
            {isWeb && paper.url && (
              <button
                className={styles.openBtn}
                onClick={() => window.open(paper.url, '_blank')}
                title="在新标签页打开"
              >
                打开
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/* ===== 主入口组件 ===== */
export default function ToolResultCard({ toolResult }) {
  if (!toolResult || !toolResult.resultType) return null;

  const { tool, resultType, content } = toolResult;

  switch (resultType) {
    case 'writing':
      return <WritingCard tool={tool} content={content} />;
    case 'citation':
      return <CitationCard tool={tool} content={content} />;
    case 'knowledge':
      return <KnowledgeCard tool={tool} content={content} />;
    case 'papers':
      return <PapersCard tool={tool} content={content} />;
    default:
      // 未知 result_type 优雅降级：尝试渲染为文本
      return (
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <span className={styles.cardTitle}>{INTENT_LABELS[tool] || tool}</span>
          </div>
          <div className={styles.writingBody}>
            {typeof content === 'string' ? content : JSON.stringify(content)}
          </div>
        </div>
      );
  }
}

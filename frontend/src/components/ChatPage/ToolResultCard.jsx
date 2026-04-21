import React, { useState, useCallback } from 'react';
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
        {text || content}
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
        <span className={styles.cardCount}>{cards.length} 条结果</span>
      </div>
      <div className={styles.cardList}>
        {cards.map((item, idx) => (
          <div key={idx} className={styles.knowledgeItem}>
            <div className={styles.knowledgeTitle}>{item.title || '无标题'}</div>
            {item.summary && (
              <div className={styles.knowledgeSummary}>{item.summary}</div>
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

/* ===== Papers 类型卡片 (recent_papers, search_papers) ===== */
function PapersCard({ tool, content }) {
  const parsed = parseContent(content);
  const papers = Array.isArray(parsed) ? parsed
    : (parsed?.papers ? parsed.papers : null);

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

  return (
    <div className={styles.card}>
      <div className={styles.cardHeader}>
        <span className={styles.cardTitle}>{INTENT_LABELS[tool] || tool}</span>
        <span className={styles.cardCount}>{papers.length} 篇论文</span>
      </div>
      <div className={styles.cardList}>
        {papers.map((paper, idx) => (
          <div key={idx} className={styles.paperItem}>
            <div className={styles.paperTitle}>{paper.title || '无标题'}</div>
            {(paper.authors || paper.author) && (
              <div className={styles.paperMeta}>
                {paper.authors || paper.author}
              </div>
            )}
            {paper.uploaded_at && (
              <div className={styles.paperTime}>
                {new Date(paper.uploaded_at).toLocaleDateString('zh-CN')}
              </div>
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

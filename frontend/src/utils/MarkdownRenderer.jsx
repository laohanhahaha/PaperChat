import React from 'react';
import ReactMarkdown from 'react-markdown';

const components = {
  // 降级标题层次（LLM 输出的 h1 在卡片中太大）
  h1: ({node, ...props}) => <h3 style={{ margin: '0.75em 0 0.5em', fontSize: '1.1em', fontWeight: 600 }} {...props} />,
  h2: ({node, ...props}) => <h4 style={{ margin: '0.5em 0 0.25em', fontSize: '1em', fontWeight: 600 }} {...props} />,
  h3: ({node, ...props}) => <h5 style={{ margin: '0.5em 0 0.25em', fontSize: '0.95em', fontWeight: 600 }} {...props} />,
  p: ({node, ...props}) => <p style={{ margin: '0.4em 0', lineHeight: 1.7 }} {...props} />,
  ul: ({node, ...props}) => <ul style={{ margin: '0.3em 0', paddingLeft: '1.5em' }} {...props} />,
  ol: ({node, ...props}) => <ol style={{ margin: '0.3em 0', paddingLeft: '1.5em' }} {...props} />,
  li: ({node, ...props}) => <li style={{ margin: '0.2em 0', lineHeight: 1.6 }} {...props} />,
  blockquote: ({node, ...props}) => <blockquote style={{ margin: '0.5em 0', padding: '0.5em 1em', borderLeft: '3px solid var(--color-accent, #007AFF)', background: 'var(--color-bg-elevated, rgba(0,0,0,0.03))', borderRadius: '0 6px 6px 0' }} {...props} />,
  code: ({node, inline, ...props}) => inline 
    ? <code style={{ background: 'var(--color-bg-elevated, rgba(0,0,0,0.06))', padding: '0.15em 0.4em', borderRadius: '4px', fontSize: '0.9em', fontFamily: 'Consolas, monospace' }} {...props} />
    : <pre style={{ background: 'var(--color-bg-elevated, #1e1e1e)', padding: '0.75em 1em', borderRadius: '8px', overflow: 'auto', fontSize: '0.85em' }}><code {...props} /></pre>,
  strong: ({node, ...props}) => <strong style={{ fontWeight: 600 }} {...props} />,
  table: ({node, ...props}) => <div style={{ overflowX: 'auto', margin: '0.5em 0' }}><table style={{ borderCollapse: 'collapse', width: '100%', fontSize: '0.9em' }} {...props} /></div>,
  th: ({node, ...props}) => <th style={{ border: '1px solid var(--color-border, #ddd)', padding: '0.4em 0.75em', background: 'var(--color-bg-elevated, #f5f5f5)', fontWeight: 600, textAlign: 'left' }} {...props} />,
  td: ({node, ...props}) => <td style={{ border: '1px solid var(--color-border, #ddd)', padding: '0.4em 0.75em' }} {...props} />,
};

export function MarkdownContent({ content, className }) {
  if (!content) return null;
  return (
    <div className={className}>
      <ReactMarkdown components={components}>{content}</ReactMarkdown>
    </div>
  );
}

export default MarkdownContent;

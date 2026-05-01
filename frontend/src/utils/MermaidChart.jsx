import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * 检测当前是否为深色模式
 * 优先读 data-theme 属性，否则回退到系统 prefers-color-scheme
 */
function isDarkMode() {
  const dataTheme = document.documentElement.getAttribute('data-theme');
  if (dataTheme === 'dark') return true;
  if (dataTheme === 'light') return false;
  // auto 或未设置 → 跟随系统
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false;
}

const MermaidChart = ({ chart }) => {
  const containerRef = useRef(null);
  const [svg, setSvg] = useState('');
  const [error, setError] = useState(null);

  const renderChart = useCallback(async () => {
    if (!chart) return;
    try {
      const mermaid = (await import('mermaid')).default;
      mermaid.initialize({
        startOnLoad: false,
        theme: isDarkMode() ? 'dark' : 'neutral',
        securityLevel: 'loose',
      });
      const id = `mermaid-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      const { svg: renderedSvg } = await mermaid.render(id, chart);
      setSvg(renderedSvg);
      setError(null);
    } catch (err) {
      console.error('Mermaid 渲染失败:', err);
      setError(err.message || String(err));
    }
  }, [chart]);

  // 渲染图表 + 监听主题变化以重新渲染
  useEffect(() => {
    renderChart();

    // 监听 data-theme 变更（MutationObserver）
    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (m.attributeName === 'data-theme') {
          renderChart();
          break;
        }
      }
    });
    observer.observe(document.documentElement, { attributes: true });

    // 监听系统配色方案变更
    const mql = window.matchMedia?.('(prefers-color-scheme: dark)');
    const handleChange = () => renderChart();
    mql?.addEventListener?.('change', handleChange);

    return () => {
      observer.disconnect();
      mql?.removeEventListener?.('change', handleChange);
    };
  }, [renderChart]);

  if (error) {
    return (
      <div style={{
        padding: '12px',
        background: 'var(--color-bg-elevated, #f5f5f5)',
        borderRadius: '8px',
        color: 'var(--text-secondary, #666)',
      }}>
        <p style={{ margin: '0 0 8px', fontWeight: 600 }}>图表渲染失败</p>
        <pre style={{ fontSize: '12px', margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          <code>{chart}</code>
        </pre>
      </div>
    );
  }

  return svg ? (
    <div
      ref={containerRef}
      dangerouslySetInnerHTML={{ __html: svg }}
      style={{
        display: 'flex',
        justifyContent: 'center',
        padding: '16px 0',
        overflow: 'auto',
      }}
    />
  ) : (
    <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-secondary, #999)' }}>
      图表加载中...
    </div>
  );
};

export default MermaidChart;

import { useRef, useEffect, useCallback } from 'react';
import * as d3 from 'd3';

/* ===== 节点类型颜色 ===== */
const NODE_COLORS = {
  concept: '#3B82F6',
  method: '#10B981',
  dataset: '#F59E0B',
  metric: '#8B5CF6',
  author: '#6B7280',
};

/* ===== 边关系样式 ===== */
const EDGE_STYLES = {
  uses:      { dash: 'none',  width: 1.5, color: '#94A3B8' },
  extends:   { dash: 'none',  width: 1.5, color: '#94A3B8' },
  improves:  { dash: 'none',  width: 3,   color: '#64748B' },
  contradicts: { dash: '6,4', width: 2, color: '#EF4444' },
  evaluates_on: { dash: '4,4', width: 1, color: '#94A3B8' },
};

const DEFAULT_EDGE = { dash: 'none', width: 1.5, color: '#94A3B8' };

/**
 * D3.js 力导向图组件
 * @param {Object} props
 * @param {Array}  props.nodes       - 节点数组 [{ id, name, node_type, description, ... }]
 * @param {Array}  props.links       - 边数组   [{ source, target, relation_type, ... }]
 * @param {Function} props.onNodeClick - 点击节点回调
 * @param {number} props.width
 * @param {number} props.height
 * @param {Set}    props.highlightIds - 需要高亮的节点 id 集合
 */
export default function ForceGraph({
  nodes = [],
  links = [],
  onNodeClick,
  width = 800,
  height = 600,
  highlightIds,
}) {
  const svgRef = useRef(null);
  const simulationRef = useRef(null);
  const gRef = useRef(null);       // <g> group for zoom/pan
  const tooltipRef = useRef(null);

  /* ---------- D3 渲染 ---------- */
  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    // 容器 <g>，用于缩放平移
    const g = svg.append('g');
    gRef.current = g;

    // tooltip div
    let tooltip = d3.select('#kg-tooltip');
    if (tooltip.empty()) {
      tooltip = d3.select('body')
        .append('div')
        .attr('id', 'kg-tooltip')
        .style('position', 'absolute')
        .style('pointer-events', 'none')
        .style('padding', '10px 14px')
        .style('background', 'rgba(30,30,40,0.95)')
        .style('border', '1px solid #444')
        .style('border-radius', '6px')
        .style('color', '#e0e0e0')
        .style('font-size', '13px')
        .style('max-width', '280px')
        .style('line-height', '1.5')
        .style('z-index', '9999')
        .style('opacity', 0)
        .style('transition', 'opacity 0.15s');
    }
    tooltipRef.current = tooltip;

    /* ===== zoom / pan ===== */
    const zoom = d3.zoom()
      .scaleExtent([0.2, 5])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });
    svg.call(zoom);

    /* ===== force simulation ===== */
    const simNodes = nodes.map(d => ({ ...d }));
    const simLinks = links.map(d => ({ ...d }));

    const simulation = d3.forceSimulation(simNodes)
      .force('link', d3.forceLink(simLinks).id(d => d.id).distance(120))
      .force('charge', d3.forceManyBody().strength(-260))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(28));

    simulationRef.current = simulation;

    /* ===== defs: 箭头标记 ===== */
    const defs = svg.append('defs');

    Object.entries(EDGE_STYLES).forEach(([type, style]) => {
      defs.append('marker')
        .attr('id', `arrow-${type}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 22)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', style.color);
    });

    /* ===== edges ===== */
    const linkSel = g.append('g')
      .selectAll('line')
      .data(simLinks)
      .join('line')
      .attr('stroke', d => (EDGE_STYLES[d.relation_type] || DEFAULT_EDGE).color)
      .attr('stroke-width', d => (EDGE_STYLES[d.relation_type] || DEFAULT_EDGE).width)
      .attr('stroke-dasharray', d => (EDGE_STYLES[d.relation_type] || DEFAULT_EDGE).dash || null)
      .attr('marker-end', d => `url(#arrow-${d.relation_type || 'uses'})`)
      .attr('opacity', 0.6);

    /* ===== nodes ===== */
    const nodeSel = g.append('g')
      .selectAll('g')
      .data(simNodes)
      .join('g')
      .style('cursor', 'pointer');

    // 圆形节点
    nodeSel.append('circle')
      .attr('r', d => Math.max(8, Math.min(6 + (d.importance || 1) * 4, 24)))
      .attr('fill', d => NODE_COLORS[d.node_type] || '#78909C')
      .attr('stroke', '#fff')
      .attr('stroke-width', 2)
      .style('filter', 'drop-shadow(0 1px 3px rgba(0,0,0,0.15))');

    // 标签
    nodeSel.append('text')
      .text(d => (d.name || '').length > 14 ? d.name.slice(0, 14) + '…' : d.name)
      .attr('dy', d => Math.max(8, Math.min(6 + (d.importance || 1) * 4, 24)) + 14)
      .attr('text-anchor', 'middle')
      .attr('fill', '#64748B')
      .attr('font-size', '11px')
      .attr('font-family', 'var(--sans, system-ui, sans-serif)')
      .style('pointer-events', 'none');

    /* ===== drag ===== */
    const drag = d3.drag()
      .on('start', (event, d) => {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on('drag', (event, d) => {
        d.fx = event.x;
        d.fy = event.y;
      })
      .on('end', (event, d) => {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
      });
    nodeSel.call(drag);

    /* ===== hover tooltip ===== */
    nodeSel
      .on('mouseover', (event, d) => {
        tooltip
          .html(`
            <div style="font-weight:600;font-size:14px;margin-bottom:4px;">${d.name || ''}</div>
            <div style="font-size:11px;color:#94A3B8;margin-bottom:4px;">类型: ${d.node_type || '未知'}</div>
            ${d.description ? `<div style="font-size:12px;color:#CBD5E1;">${d.description}</div>` : ''}
          `)
          .style('left', (event.pageX + 14) + 'px')
          .style('top', (event.pageY - 10) + 'px')
          .style('opacity', 1);
      })
      .on('mousemove', (event) => {
        tooltip
          .style('left', (event.pageX + 14) + 'px')
          .style('top', (event.pageY - 10) + 'px');
      })
      .on('mouseout', () => {
        tooltip.style('opacity', 0);
      });

    /* ===== click ===== */
    nodeSel.on('click', (event, d) => {
      if (onNodeClick) onNodeClick(d);
    });

    /* ===== tick ===== */
    simulation.on('tick', () => {
      linkSel
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);

      nodeSel.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    /* ===== 高亮 ===== */
    const applyHighlight = () => {
      if (!highlightIds || highlightIds.size === 0) {
        nodeSel.select('circle').attr('opacity', 1);
        linkSel.attr('opacity', 0.6);
        nodeSel.select('text').attr('opacity', 1);
        return;
      }
      nodeSel.select('circle')
        .attr('opacity', d => highlightIds.has(d.id) ? 1 : 0.15);
      nodeSel.select('text')
        .attr('opacity', d => highlightIds.has(d.id) ? 1 : 0.15);
      linkSel.attr('opacity', d => {
        const sid = typeof d.source === 'object' ? d.source.id : d.source;
        const tid = typeof d.target === 'object' ? d.target.id : d.target;
        return (highlightIds.has(sid) || highlightIds.has(tid)) ? 0.6 : 0.06;
      });
    };
    applyHighlight();

    /* ===== cleanup ===== */
    return () => {
      simulation.stop();
      tooltip.style('opacity', 0);
    };
  }, [nodes, links, width, height, onNodeClick, highlightIds]);

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      style={{ background: '#f8fafc', borderRadius: '8px' }}
    />
  );
}

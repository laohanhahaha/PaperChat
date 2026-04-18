import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactECharts from 'echarts-for-react';
// ECharts 按需导入，减少打包体积
import * as echarts from 'echarts/core';
import { GraphChart } from 'echarts/charts';
import {
  TooltipComponent,
  LegendComponent,
  TitleComponent
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

// 注册 ECharts 组件
const echartsInstance = (() => {
  echarts.use([
    GraphChart,
    TooltipComponent,
    LegendComponent,
    TitleComponent,
    CanvasRenderer
  ]);
  return echarts;
})();

import useKnowledgeStore from '../stores/knowledgeStore';
import usePaperStore from '../stores/paperStore';
import KnowledgeCardEditor from '../components/KnowledgeCardEditor/KnowledgeCardEditor';
import styles from './KnowledgeGraphPage.module.css';

// 关系类型映射
const RELATION_TYPE_MAP = {
    'related': { label: '相关', color: '#64B5F6' },
    'prerequisite': { label: '前置', color: '#81C784' },
    'extends': { label: '扩展', color: '#BA68C8' },
    'supports': { label: '支持', color: '#4DD0E1' },
    'contradicts': { label: '矛盾', color: '#E57373' }
};

// 分类颜色映射
const CATEGORY_COLORS = [
    '#64B5F6', '#81C784', '#BA68C8', '#4DD0E1', '#FFD54F',
    '#FF8A65', '#A5D6A7', '#F06292', '#7986CB', '#4DB6AC'
];

// 获取分类颜色
const getCategoryColor = (category, categories) => {
    if (!category) return '#78909C';
    const index = categories.indexOf(category);
    return CATEGORY_COLORS[index % CATEGORY_COLORS.length] || '#78909C';
};

// 获取关系标签
const getRelationLabel = (relationType) => {
    return RELATION_TYPE_MAP[relationType]?.label || relationType;
};

// 格式化日期
const formatDate = (dateString) => {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
};

export default function KnowledgeGraphPage() {
    const navigate = useNavigate();
    const chartRef = useRef(null);
    
    const {
        graphData,
        loading,
        error,
        fetchGraphData,
        fetchStats,
        deleteCard,
        findRelations
    } = useKnowledgeStore();
    
    const { papers, fetchPapers } = usePaperStore();
    
    // 状态
    const [selectedNode, setSelectedNode] = useState(null);
    const [detailPanelOpen, setDetailPanelOpen] = useState(false);
    const [editorOpen, setEditorOpen] = useState(false);
    const [editingCard, setEditingCard] = useState(null);
    
    // 筛选状态
    const [filters, setFilters] = useState({
        paperId: '',
        tag: '',
        category: ''
    });
    
    // 布局状态
    const [layout, setLayout] = useState('force'); // 'force' | 'circular'
    const [isFullscreen, setIsFullscreen] = useState(false);
    
    // 加载数据
    useEffect(() => {
        fetchGraphData();
        fetchStats();
        fetchPapers();
    }, [fetchGraphData, fetchStats, fetchPapers]);
    
    // 获取所有分类
    const categories = useMemo(() => {
        if (!graphData?.nodes) return [];
        const cats = new Set(graphData.nodes.map(n => n.category).filter(Boolean));
        return Array.from(cats);
    }, [graphData]);
    
    // 获取所有标签
    const allTags = useMemo(() => {
        if (!graphData?.nodes) return [];
        const tags = new Set();
        graphData.nodes.forEach(n => {
            n.tags?.forEach(t => tags.add(t));
        });
        return Array.from(tags);
    }, [graphData]);
    
    // 过滤后的节点和边
    const filteredData = useMemo(() => {
        if (!graphData) return { nodes: [], edges: [] };
        
        let filteredNodes = graphData.nodes;
        
        // 按论文筛选
        if (filters.paperId) {
            filteredNodes = filteredNodes.filter(n => n.paper_id === parseInt(filters.paperId));
        }
        
        // 按标签筛选
        if (filters.tag) {
            filteredNodes = filteredNodes.filter(n => n.tags?.includes(filters.tag));
        }
        
        // 按分类筛选
        if (filters.category) {
            filteredNodes = filteredNodes.filter(n => n.category === filters.category);
        }
        
        // 过滤边（只保留两端节点都存在的边）
        const nodeIds = new Set(filteredNodes.map(n => n.id));
        const filteredEdges = graphData.edges.filter(
            e => nodeIds.has(e.source) && nodeIds.has(e.target)
        );
        
        return { nodes: filteredNodes, edges: filteredEdges };
    }, [graphData, filters]);
    
    // 转换为 ECharts 数据格式
    const chartData = useMemo(() => {
        const nodes = filteredData.nodes.map(node => ({
            id: String(node.id),
            name: node.title,
            summary: node.summary,
            category: node.category || '未分类',
            symbolSize: Math.min(20 + (node.importance || 1) * 8, 50),
            value: node.importance || 1,
            itemStyle: {
                color: getCategoryColor(node.category, categories)
            },
            ...node
        }));
        
        const links = filteredData.edges.map(edge => ({
            source: String(edge.source),
            target: String(edge.target),
            relationType: edge.type,
            relationLabel: getRelationLabel(edge.type),
            lineStyle: {
                color: RELATION_TYPE_MAP[edge.type]?.color || '#999',
                curveness: 0.3
            },
            label: {
                show: true,
                formatter: getRelationLabel(edge.type),
                fontSize: 10,
                color: '#aaa'
            }
        }));
        
        // ECharts categories
        const chartCategories = categories.map((cat, index) => ({
            name: cat,
            itemStyle: { color: CATEGORY_COLORS[index % CATEGORY_COLORS.length] }
        }));
        chartCategories.unshift({ name: '未分类', itemStyle: { color: '#78909C' } });
        
        return { nodes, links, categories: chartCategories };
    }, [filteredData, categories]);
    
    // ECharts 配置
    const getOption = useCallback(() => {
        return {
            backgroundColor: 'transparent',
            tooltip: {
                trigger: 'item',
                backgroundColor: 'rgba(30, 30, 40, 0.95)',
                borderColor: '#444',
                borderWidth: 1,
                textStyle: { color: '#e0e0e0' },
                formatter: (params) => {
                    if (params.dataType === 'node') {
                        return `<div style="max-width: 280px;">
                            <b style="font-size: 14px;">${params.data.name}</b>
                            ${params.data.summary ? `<p style="margin: 6px 0 0; color: #aaa; font-size: 12px;">${params.data.summary}</p>` : ''}
                            <div style="margin-top: 8px; color: #888; font-size: 11px;">
                                分类: ${params.data.category || '未分类'}<br/>
                                重要性: ${params.data.value?.toFixed(1) || '1.0'}
                            </div>
                        </div>`;
                    }
                    return `<div>
                        <b>${params.data.relationLabel}</b>
                        <div style="color: #888; font-size: 11px; margin-top: 4px;">
                            ${chartData.nodes.find(n => n.id === params.data.source)?.name || ''} 
                            → 
                            ${chartData.nodes.find(n => n.id === params.data.target)?.name || ''}
                        </div>
                    </div>`;
                }
            },
            legend: {
                show: true,
                orient: 'vertical',
                right: 10,
                top: 60,
                data: chartData.categories.map(c => c.name),
                textStyle: { color: '#aaa', fontSize: 11 },
                selectedMode: false
            },
            series: [{
                type: 'graph',
                layout: layout,
                roam: true,
                draggable: true,
                emphasis: {
                    focus: 'adjacency',
                    lineStyle: { width: 3 }
                },
                force: layout === 'force' ? {
                    repulsion: 300,
                    edgeLength: [80, 180],
                    gravity: 0.15,
                    layoutAnimation: true
                } : undefined,
                circular: layout === 'circular' ? {
                    rotateLabel: true
                } : undefined,
                data: chartData.nodes,
                links: chartData.links,
                categories: chartData.categories,
                label: {
                    show: true,
                    position: 'right',
                    fontSize: 12,
                    color: '#e0e0e0',
                    formatter: '{b}'
                },
                edgeSymbol: ['none', 'arrow'],
                edgeSymbolSize: [4, 8],
                lineStyle: {
                    opacity: 0.6,
                    curveness: 0.3
                },
                itemStyle: {
                    borderColor: '#222',
                    borderWidth: 2
                }
            }],
            animationDuration: 1000,
            animationEasingUpdate: 'quinticInOut'
        };
    }, [chartData, layout]);
    
    // 处理节点点击
    const handleNodeClick = useCallback((params) => {
        if (params.dataType === 'node') {
            setSelectedNode(params.data);
            setDetailPanelOpen(true);
        }
    }, []);
    
    // 处理节点双击
    const handleNodeDoubleClick = useCallback((params) => {
        if (params.dataType === 'node' && params.data.paper_id) {
            navigate(`/reader/${params.data.paper_id}`);
        }
    }, [navigate]);
    
    // 处理图表事件
    const onEvents = useMemo(() => ({
        click: handleNodeClick,
        dblclick: handleNodeDoubleClick
    }), [handleNodeClick, handleNodeDoubleClick]);
    
    // 缩放控制
    const handleZoom = useCallback((action) => {
        const instance = chartRef.current?.getEchartsInstance();
        if (!instance) return;
        
        const option = instance.getOption();
        const currentZoom = option.series[0].zoom || 1;
        
        if (action === 'in') {
            instance.setOption({
                series: [{ zoom: currentZoom * 1.2 }]
            });
        } else if (action === 'out') {
            instance.setOption({
                series: [{ zoom: currentZoom / 1.2 }]
            });
        } else if (action === 'reset') {
            instance.setOption({
                series: [{ zoom: 1, center: undefined }]
            });
        }
    }, []);
    
    // 切换全屏
    const toggleFullscreen = useCallback(() => {
        if (!document.fullscreenElement) {
            document.documentElement.requestFullscreen();
            setIsFullscreen(true);
        } else {
            document.exitFullscreen();
            setIsFullscreen(false);
        }
    }, []);
    
    // 清除筛选
    const clearFilters = useCallback(() => {
        setFilters({ paperId: '', tag: '', category: '' });
    }, []);
    
    // 编辑卡片
    const handleEditCard = useCallback(() => {
        if (!selectedNode) return;
        setEditingCard({
            id: selectedNode.id,
            title: selectedNode.name,
            summary: selectedNode.summary,
            content: selectedNode.content,
            tags: selectedNode.tags,
            category: selectedNode.category,
            importance: selectedNode.importance,
            paper_id: selectedNode.paper_id
        });
        setEditorOpen(true);
    }, [selectedNode]);
    
    // 删除卡片
    const handleDeleteCard = useCallback(async () => {
        if (!selectedNode) return;
        if (!window.confirm('确定要删除这张知识卡片吗？')) return;
        
        try {
            await deleteCard(parseInt(selectedNode.id));
            setSelectedNode(null);
            setDetailPanelOpen(false);
            fetchGraphData();
        } catch (err) {
            console.error('删除失败:', err);
        }
    }, [selectedNode, deleteCard, fetchGraphData]);
    
    // 发现关联
    const handleFindRelations = useCallback(async () => {
        if (!selectedNode) return;
        try {
            const relations = await findRelations(parseInt(selectedNode.id));
            if (relations.length > 0) {
                alert(`发现 ${relations.length} 个新关联！`);
                fetchGraphData();
            } else {
                alert('未发现新的关联');
            }
        } catch (err) {
            console.error('发现关联失败:', err);
        }
    }, [selectedNode, findRelations, fetchGraphData]);
    
    // 查看论文
    const handleViewPaper = useCallback(() => {
        if (selectedNode?.paper_id) {
            navigate(`/reader/${selectedNode.paper_id}`);
        }
    }, [selectedNode, navigate]);
    
    // 关闭编辑器
    const handleCloseEditor = useCallback(() => {
        setEditorOpen(false);
        setEditingCard(null);
    }, []);
    
    // 保存编辑器后刷新
    const handleSaveEditor = useCallback(() => {
        fetchGraphData();
    }, [fetchGraphData]);

    return (
        <div className={`${styles.container} ${isFullscreen ? styles.fullscreen : ''}`}>
            {/* 顶部工具栏 */}
            <header className={styles.header}>
                <div className={styles.headerLeft}>
                    <h1 className={styles.title}>🕸️ 知识图谱</h1>
                    <span className={styles.stats}>
                        {filteredData.nodes.length} 个节点 · {filteredData.edges.length} 条关联
                    </span>
                </div>
                <div className={styles.headerRight}>
                    
                </div>
            </header>
            
            {/* 工具栏 */}
            <div className={styles.toolbar}>
                <div className={styles.filters}>
                    {/* 论文筛选 */}
                    <select
                        value={filters.paperId}
                        onChange={(e) => setFilters(f => ({ ...f, paperId: e.target.value }))}
                        className={styles.filterSelect}
                    >
                        <option value="">所有论文</option>
                        {papers.map(paper => (
                            <option key={paper.id} value={paper.id}>
                                {paper.title?.slice(0, 30)}...
                            </option>
                        ))}
                    </select>
                    
                    {/* 标签筛选 */}
                    <select
                        value={filters.tag}
                        onChange={(e) => setFilters(f => ({ ...f, tag: e.target.value }))}
                        className={styles.filterSelect}
                    >
                        <option value="">所有标签</option>
                        {allTags.map(tag => (
                            <option key={tag} value={tag}>{tag}</option>
                        ))}
                    </select>
                    
                    {/* 分类筛选 */}
                    <select
                        value={filters.category}
                        onChange={(e) => setFilters(f => ({ ...f, category: e.target.value }))}
                        className={styles.filterSelect}
                    >
                        <option value="">所有分类</option>
                        {categories.map(cat => (
                            <option key={cat} value={cat}>{cat}</option>
                        ))}
                    </select>
                    
                    {(filters.paperId || filters.tag || filters.category) && (
                        <button onClick={clearFilters} className={styles.clearBtn}>
                            清除筛选
                        </button>
                    )}
                </div>
                
                <div className={styles.tools}>
                    {/* 布局切换 */}
                    <div className={styles.layoutToggle}>
                        <button 
                            className={`${styles.layoutBtn} ${layout === 'force' ? styles.active : ''}`}
                            onClick={() => setLayout('force')}
                            title="力导向布局"
                        >
                            ⊞ 力导向
                        </button>
                        <button 
                            className={`${styles.layoutBtn} ${layout === 'circular' ? styles.active : ''}`}
                            onClick={() => setLayout('circular')}
                            title="环形布局"
                        >
                            ◎ 环形
                        </button>
                    </div>
                    
                    {/* 缩放控制 */}
                    <div className={styles.zoomControls}>
                        <button onClick={() => handleZoom('in')} title="放大">+</button>
                        <button onClick={() => handleZoom('reset')} title="重置">⟲</button>
                        <button onClick={() => handleZoom('out')} title="缩小">−</button>
                    </div>
                    
                    {/* 全屏按钮 */}
                    <button 
                        className={styles.fullscreenBtn}
                        onClick={toggleFullscreen}
                        title={isFullscreen ? '退出全屏' : '全屏'}
                    >
                        {isFullscreen ? '⛶ 退出' : '⛶ 全屏'}
                    </button>
                </div>
            </div>
            
            {/* 主体内容 */}
            <div className={styles.main}>
                {/* 加载状态 */}
                {loading && !graphData && (
                    <div className={styles.loading}>
                        <div className={styles.spinner}></div>
                        <p>加载知识图谱...</p>
                    </div>
                )}
                
                {/* 错误状态 */}
                {error && (
                    <div className={styles.error}>
                        <p>{error}</p>
                        <button onClick={() => fetchGraphData()}>重试</button>
                    </div>
                )}
                
                {/* 空状态 */}
                {!loading && filteredData.nodes.length === 0 && (
                    <div className={styles.empty}>
                        <div className={styles.emptyIcon}>🕸️</div>
                        <p>暂无知识图谱数据</p>
                        <p className={styles.emptyHint}>
                            {graphData?.nodes?.length > 0 
                                ? '当前筛选条件下无匹配节点' 
                                : '创建知识卡片后，图谱将自动生成'}
                        </p>
                        {graphData?.nodes?.length > 0 && (
                            <button onClick={clearFilters} className={styles.clearFilterBtn}>
                                清除筛选
                            </button>
                        )}
                    </div>
                )}
                
                {/* ECharts 图表 */}
                {!loading && filteredData.nodes.length > 0 && (
                    <ReactECharts
                        ref={chartRef}
                        echarts={echartsInstance}
                        option={getOption()}
                        onEvents={onEvents}
                        style={{ width: '100%', height: '100%' }}
                        notMerge={true}
                        lazyUpdate={true}
                    />
                )}
                
                {/* 右侧详情面板 */}
                {detailPanelOpen && selectedNode && (
                    <aside className={`${styles.detailPanel} ${detailPanelOpen ? styles.open : ''}`}>
                        <div className={styles.detailHeader}>
                            <h3>{selectedNode.name}</h3>
                            <button 
                                className={styles.closeBtn}
                                onClick={() => setDetailPanelOpen(false)}
                            >
                                ×
                            </button>
                        </div>
                        
                        <div className={styles.detailContent}>
                            {/* 摘要 */}
                            {selectedNode.summary && (
                                <div className={styles.detailSection}>
                                    <h4>摘要</h4>
                                    <p>{selectedNode.summary}</p>
                                </div>
                            )}
                            
                            {/* 内容 */}
                            {selectedNode.content && (
                                <div className={styles.detailSection}>
                                    <h4>内容</h4>
                                    <p className={styles.contentText}>{selectedNode.content}</p>
                                </div>
                            )}
                            
                            {/* 标签 */}
                            {selectedNode.tags?.length > 0 && (
                                <div className={styles.detailSection}>
                                    <h4>标签</h4>
                                    <div className={styles.tags}>
                                        {selectedNode.tags.map(tag => (
                                            <span key={tag} className={styles.tag}>{tag}</span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            
                            {/* 元信息 */}
                            <div className={styles.detailSection}>
                                <h4>属性</h4>
                                <div className={styles.meta}>
                                    <div className={styles.metaItem}>
                                        <span className={styles.metaLabel}>分类</span>
                                        <span className={styles.metaValue}>
                                            {selectedNode.category || '未分类'}
                                        </span>
                                    </div>
                                    <div className={styles.metaItem}>
                                        <span className={styles.metaLabel}>重要性</span>
                                        <span className={styles.metaValue}>
                                            {selectedNode.importance?.toFixed(1) || '1.0'}
                                        </span>
                                    </div>
                                    {selectedNode.source_type && (
                                        <div className={styles.metaItem}>
                                            <span className={styles.metaLabel}>来源</span>
                                            <span className={styles.metaValue}>
                                                {selectedNode.source_type === 'highlight' ? '📌 高亮' :
                                                 selectedNode.source_type === 'chat' ? '💬 问答' :
                                                 selectedNode.source_type === 'manual' ? '✏️ 手动' :
                                                 selectedNode.source_type === 'analysis' ? '🔬 分析' : 
                                                 selectedNode.source_type}
                                            </span>
                                        </div>
                                    )}
                                    {selectedNode.created_at && (
                                        <div className={styles.metaItem}>
                                            <span className={styles.metaLabel}>创建时间</span>
                                            <span className={styles.metaValue}>
                                                {formatDate(selectedNode.created_at)}
                                            </span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                        
                        {/* 操作按钮 */}
                        <div className={styles.detailActions}>
                            {selectedNode.paper_id && (
                                <button 
                                    className={styles.actionBtn}
                                    onClick={handleViewPaper}
                                >
                                    📄 查看论文
                                </button>
                            )}
                            <button 
                                className={styles.actionBtn}
                                onClick={handleEditCard}
                            >
                                ✏️ 编辑
                            </button>
                            <button 
                                className={styles.actionBtn}
                                onClick={handleFindRelations}
                            >
                                🔗 发现关联
                            </button>
                            <button 
                                className={`${styles.actionBtn} ${styles.deleteBtn}`}
                                onClick={handleDeleteCard}
                            >
                                🗑️ 删除
                            </button>
                        </div>
                    </aside>
                )}
            </div>
            
            {/* 提示信息 */}
            <div className={styles.hints}>
                <span>单击节点查看详情</span>
                <span>双击节点跳转论文</span>
                <span>拖拽节点调整位置</span>
                <span>滚轮缩放图谱</span>
            </div>
            
            {/* 卡片编辑器弹窗 */}
            {editorOpen && (
                <KnowledgeCardEditor
                    card={editingCard}
                    onClose={handleCloseEditor}
                    onSave={handleSaveEditor}
                    isNew={false}
                />
            )}
        </div>
    );
}

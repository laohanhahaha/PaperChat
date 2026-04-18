import { useState, useEffect, useCallback, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import useKnowledgeStore from '../stores/knowledgeStore';
import KnowledgeCardEditor from '../components/KnowledgeCardEditor/KnowledgeCardEditor';
import styles from './KnowledgePage.module.css';

// 来源类型映射
const SOURCE_TYPE_MAP = {
    'highlight': { label: '高亮', icon: '📌', color: '#FF9800' },
    'chat': { label: '问答', icon: '💬', color: '#2196F3' },
    'manual': { label: '手动', icon: '✏️', color: '#4CAF50' },
    'analysis': { label: '分析', icon: '🔬', color: '#9C27B0' }
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

// 截断文本
const truncateText = (text, maxLength = 100) => {
    if (!text) return '';
    if (text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
};

// 知识卡片组件 - 使用 React.memo 优化渲染性能
const KnowledgeCard = memo(({ card, viewMode, onEdit, onDelete }) => {
    const [expanded, setExpanded] = useState(false);

    const sourceInfo = SOURCE_TYPE_MAP[card.source_type] || { label: '未知', icon: '📄', color: '#999' };

    const handleToggleExpand = useCallback(() => {
        setExpanded(prev => !prev);
    }, []);

    // 使用 useCallback 包装事件处理函数，确保引用稳定
    const handleEdit = useCallback(() => {
        onEdit(card);
    }, [onEdit, card]);

    const handleDelete = useCallback(() => {
        onDelete(card.id);
    }, [onDelete, card.id]);

    if (viewMode === 'list') {
        return (
            <div className={styles.listCard}>
                <div className={styles.listCardHeader}>
                    <h3 className={styles.cardTitle} onClick={handleEdit}>
                        {sourceInfo.icon} {card.title}
                    </h3>
                    <div className={styles.cardActions}>
                        <button onClick={handleEdit} className={styles.actionBtn} title="编辑">
                            ✏️
                        </button>
                        <button onClick={handleDelete} className={styles.actionBtn} title="删除">
                            🗑️
                        </button>
                    </div>
                </div>
                <p className={styles.cardSummary}>{card.summary || truncateText(card.content, 150)}</p>
                <div className={styles.cardMeta}>
                    {card.tags?.map(tag => (
                        <span key={tag} className={styles.tag}>{tag}</span>
                    ))}
                    <span className={styles.cardDate}>{formatDate(card.created_at)}</span>
                </div>
            </div>
        );
    }

    return (
        <div className={styles.card}>
            <div className={styles.cardHeader}>
                <span
                    className={styles.sourceBadge}
                    style={{ backgroundColor: sourceInfo.color + '20', color: sourceInfo.color }}
                >
                    {sourceInfo.icon} {sourceInfo.label}
                </span>
                <div className={styles.cardActions}>
                    <button onClick={handleEdit} className={styles.actionBtn} title="编辑">
                        ✏️
                    </button>
                    <button onClick={handleDelete} className={styles.actionBtn} title="删除">
                        🗑️
                    </button>
                </div>
            </div>

            <h3 className={styles.cardTitle} onClick={handleToggleExpand}>
                {card.title}
            </h3>

            <p className={styles.cardContent}>
                {expanded ? card.content : truncateText(card.summary || card.content, 120)}
            </p>

            {card.content.length > 120 && (
                <button
                    className={styles.expandBtn}
                    onClick={handleToggleExpand}
                >
                    {expanded ? '收起' : '展开'}
                </button>
            )}

            <div className={styles.cardFooter}>
                <div className={styles.cardTags}>
                    {card.tags?.slice(0, 3).map(tag => (
                        <span key={tag} className={styles.tag}>{tag}</span>
                    ))}
                    {card.tags?.length > 3 && (
                        <span className={styles.tagMore}>+{card.tags.length - 3}</span>
                    )}
                </div>
                <span className={styles.cardDate}>{formatDate(card.created_at)}</span>
            </div>
        </div>
    );
});

export default function KnowledgePage() {
    useNavigate();
    const {
        cards,
        totalCount,
        stats,
        loading,
        error,
        filters,
        currentPage,
        pageSize,
        fetchCards,
        fetchStats,
        deleteCard,
        searchCards,
        setFilters,
        clearFilters
    } = useKnowledgeStore();

    const [editorOpen, setEditorOpen] = useState(false);
    const [editingCard, setEditingCard] = useState(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [viewMode, setViewMode] = useState('grid'); // 'grid' | 'list'

    // 加载数据
    useEffect(() => {
        fetchCards();
        fetchStats();
    }, [fetchCards, fetchStats]);

    // 搜索防抖（300ms）
    useEffect(() => {
        const timer = setTimeout(() => {
            if (searchQuery.trim()) {
                searchCards(searchQuery);
            }
        }, 300);
        return () => clearTimeout(timer);
    }, [searchQuery, searchCards]);

    // 处理创建卡片
    const handleCreateCard = useCallback(() => {
        setEditingCard(null);
        setEditorOpen(true);
    }, []);

    // 处理编辑卡片
    const handleEditCard = useCallback((card) => {
        setEditingCard(card);
        setEditorOpen(true);
    }, []);

    // 处理删除卡片
    const handleDeleteCard = useCallback(async (cardId) => {
        if (!window.confirm('确定要删除这张知识卡片吗？')) return;
        
        try {
            await deleteCard(cardId);
        } catch (err) {
            console.error('删除失败:', err);
        }
    }, [deleteCard]);

    // 处理关闭编辑器
    const handleCloseEditor = useCallback(() => {
        setEditorOpen(false);
        setEditingCard(null);
    }, []);

    // 处理搜索
    const handleSearch = useCallback((e) => {
        const value = e.target.value;
        setSearchQuery(value);
        setFilters({ search: value });
    }, [setFilters]);

    // 处理筛选
    const handleFilterChange = useCallback((key, value) => {
        setFilters({ [key]: value || null });
    }, [setFilters]);

    // 清除所有筛选
    const handleClearFilters = useCallback(() => {
        setSearchQuery('');
        clearFilters();
    }, [clearFilters]);

    // 处理分页
    const handlePageChange = useCallback((newPage) => {
        fetchCards({ page: newPage });
    }, [fetchCards]);

    // 获取所有可用标签
    const allTags = stats?.tag_cloud ? Object.keys(stats.tag_cloud) : [];
    const allCategories = stats?.category_stats ? Object.keys(stats.category_stats) : [];

    return (
        <div className={styles.container}>
            {/* 顶部工具栏 */}
            <header className={styles.header}>
                <h1 className={styles.title}>📚 我的知识库</h1>
                <p className={styles.subtitle}>共 {totalCount} 张知识卡片</p>
            </header>

            {/* 搜索和筛选栏 */}
            <div className={styles.toolbar}>
                <div className={styles.searchBox}>
                    <input
                        type="text"
                        placeholder="搜索知识卡片..."
                        value={searchQuery}
                        onChange={handleSearch}
                        className={styles.searchInput}
                    />
                    <span className={styles.searchIcon}>🔍</span>
                </div>

                <div className={styles.filters}>
                    <select
                        value={filters.category || ''}
                        onChange={(e) => handleFilterChange('category', e.target.value)}
                        className={styles.filterSelect}
                    >
                        <option value="">所有分类</option>
                        {allCategories.map(cat => (
                            <option key={cat} value={cat}>{cat}</option>
                        ))}
                    </select>

                    <select
                        value={filters.sourceType || ''}
                        onChange={(e) => handleFilterChange('sourceType', e.target.value)}
                        className={styles.filterSelect}
                    >
                        <option value="">所有来源</option>
                        <option value="highlight">📌 高亮</option>
                        <option value="chat">💬 问答</option>
                        <option value="manual">✏️ 手动</option>
                        <option value="analysis">🔬 分析</option>
                    </select>

                    <select
                        value={filters.tag || ''}
                        onChange={(e) => handleFilterChange('tag', e.target.value)}
                        className={styles.filterSelect}
                    >
                        <option value="">所有标签</option>
                        {allTags.map(tag => (
                            <option key={tag} value={tag}>{tag}</option>
                        ))}
                    </select>

                    {(filters.search || filters.category || filters.sourceType || filters.tag) && (
                        <button onClick={handleClearFilters} className={styles.clearBtn}>
                            清除筛选
                        </button>
                    )}
                </div>

                <div className={styles.actions}>
                    <button
                        onClick={() => setViewMode(viewMode === 'grid' ? 'list' : 'grid')}
                        className={styles.viewModeBtn}
                    >
                        {viewMode === 'grid' ? '☰ 列表' : '⊞ 网格'}
                    </button>
                    <button onClick={handleCreateCard} className={styles.createBtn}>
                        + 新建卡片
                    </button>
                </div>
            </div>

            {/* 主体内容 */}
            <div className={styles.main}>
                {/* 卡片列表 */}
                <div className={styles.content}>
                    {loading ? (
                        <div className={styles.loading}>
                            <div className={styles.spinner}></div>
                            <p>加载中...</p>
                        </div>
                    ) : error ? (
                        <div className={styles.error}>
                            <p>{error}</p>
                            <button onClick={() => fetchCards()}>重试</button>
                        </div>
                    ) : cards.length === 0 ? (
                        <div className={styles.empty}>
                            <div className={styles.emptyIcon}>📚</div>
                            <p>暂无知识卡片</p>
                            <p className={styles.emptyHint}>
                                点击"新建卡片"开始创建，或从高亮/问答中提取知识
                            </p>
                        </div>
                    ) : (
                        <>
                            <div className={viewMode === 'grid' ? styles.grid : styles.list}>
                                {cards.map(card => (
                                    <KnowledgeCard
                                        key={card.id}
                                        card={card}
                                        viewMode={viewMode}
                                        onEdit={handleEditCard}
                                        onDelete={handleDeleteCard}
                                    />
                                ))}
                            </div>

                            {/* 分页 */}
                            {totalCount > pageSize && (
                                <div className={styles.pagination}>
                                    <button
                                        disabled={currentPage === 1}
                                        onClick={() => handlePageChange(currentPage - 1)}
                                    >
                                        上一页
                                    </button>
                                    <span>
                                        第 {currentPage} 页 / 共 {Math.ceil(totalCount / pageSize)} 页
                                    </span>
                                    <button
                                        disabled={currentPage >= Math.ceil(totalCount / pageSize)}
                                        onClick={() => handlePageChange(currentPage + 1)}
                                    >
                                        下一页
                                    </button>
                                </div>
                            )}
                        </>
                    )}
                </div>

                {/* 侧边栏统计 */}
                <aside className={styles.sidebar}>
                    <div className={styles.statsCard}>
                        <h3>📊 统计信息</h3>
                        <div className={styles.statItem}>
                            <span className={styles.statLabel}>总卡片数</span>
                            <span className={styles.statValue}>{stats?.total_cards || 0}</span>
                        </div>
                        <div className={styles.statItem}>
                            <span className={styles.statLabel}>关联关系</span>
                            <span className={styles.statValue}>{stats?.total_relations || 0}</span>
                        </div>
                    </div>

                    {stats?.category_stats && Object.keys(stats.category_stats).length > 0 && (
                        <div className={styles.statsCard}>
                            <h3>📁 分类分布</h3>
                            {Object.entries(stats.category_stats).map(([cat, count]) => (
                                <div key={cat} className={styles.statItem}>
                                    <span className={styles.statLabel}>{cat || '未分类'}</span>
                                    <span className={styles.statValue}>{count}</span>
                                </div>
                            ))}
                        </div>
                    )}

                    {stats?.source_stats && Object.keys(stats.source_stats).length > 0 && (
                        <div className={styles.statsCard}>
                            <h3>📌 来源分布</h3>
                            {Object.entries(stats.source_stats).map(([src, count]) => {
                                const info = SOURCE_TYPE_MAP[src] || { label: src || '未知', icon: '📄' };
                                return (
                                    <div key={src} className={styles.statItem}>
                                        <span className={styles.statLabel}>
                                            {info.icon} {info.label}
                                        </span>
                                        <span className={styles.statValue}>{count}</span>
                                    </div>
                                );
                            })}
                        </div>
                    )}

                    {stats?.tag_cloud && Object.keys(stats.tag_cloud).length > 0 && (
                        <div className={styles.statsCard}>
                            <h3>🏷️ 标签云</h3>
                            <div className={styles.tagCloud}>
                                {Object.entries(stats.tag_cloud)
                                    .sort((a, b) => b[1] - a[1])
                                    .slice(0, 20)
                                    .map(([tag, count]) => (
                                        <span
                                            key={tag}
                                            className={styles.tagCloudItem}
                                            onClick={() => handleFilterChange('tag', tag)}
                                            style={{
                                                fontSize: `${Math.max(0.8, Math.min(1.5, 0.8 + count * 0.1))}rem`,
                                                opacity: Math.max(0.6, Math.min(1, 0.6 + count * 0.1))
                                            }}
                                        >
                                            {tag}
                                        </span>
                                    ))}
                            </div>
                        </div>
                    )}
                </aside>
            </div>

            {/* 卡片编辑器弹窗 */}
            {editorOpen && (
                <KnowledgeCardEditor
                    card={editingCard}
                    onClose={handleCloseEditor}
                    isNew={!editingCard}
                />
            )}
        </div>
    );
}



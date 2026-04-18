import { useState, useEffect, useCallback, useRef } from 'react';
import useKnowledgeStore from '../../stores/knowledgeStore';
import usePaperStore from '../../stores/paperStore';
import styles from './KnowledgeCardEditor.module.css';

// 来源类型选项
const SOURCE_TYPES = [
    { value: 'manual', label: '✏️ 手动创建' },
    { value: 'highlight', label: '📌 高亮提取' },
    { value: 'chat', label: '💬 问答提取' },
    { value: 'analysis', label: '🔬 分析提取' }
];

// 关联类型选项
const RELATION_TYPES = [
    { value: 'related', label: '相关' },
    { value: 'prerequisite', label: '前置知识' },
    { value: 'extends', label: '扩展' },
    { value: 'supports', label: '支持' },
    { value: 'contradicts', label: '矛盾' }
];

export default function KnowledgeCardEditor({ card, onClose, isNew = false }) {
    const {
        createCard,
        updateCard,
        autoTag,
        findRelations,
        fetchCardRelations,
        createRelation,
        deleteRelation,
        cards,
        loading
    } = useKnowledgeStore();
    
    const { papers } = usePaperStore();
    
    // 表单状态
    const [formData, setFormData] = useState({
        title: '',
        content: '',
        summary: '',
        tags: [],
        category: '',
        source_type: 'manual',
        paper_id: null,
        importance: 1.0
    });
    
    // 标签输入
    const [tagInput, setTagInput] = useState('');
    
    // 发现的关联
    const [discoveredRelations, setDiscoveredRelations] = useState([]);
    const [existingRelations, setExistingRelations] = useState([]);
    const [showRelations, setShowRelations] = useState(false);
    
    // 加载现有关联
    const loadExistingRelations = useCallback(async (cardId) => {
        try {
            const relations = await fetchCardRelations(cardId);
            setExistingRelations(relations);
        } catch (_err) {
            console.error('加载关联失败:', _err);
        }
    }, [fetchCardRelations]);
    
    // 使用 ref 追踪 card 变化，避免在 effect 中直接 setState
    const prevCardIdRef = useRef(null);
    
    useEffect(() => {
        if (card && card.id !== prevCardIdRef.current) {
            prevCardIdRef.current = card.id;
            // 使用 setTimeout 将 setState 移出渲染阶段
            const timer = setTimeout(() => {
                setFormData({
                    title: card.title || '',
                    content: card.content || '',
                    summary: card.summary || '',
                    tags: card.tags || [],
                    category: card.category || '',
                    source_type: card.source_type || 'manual',
                    paper_id: card.paper_id || null,
                    importance: card.importance || 1.0
                });
                loadExistingRelations(card.id);
            }, 0);
            return () => clearTimeout(timer);
        }
    }, [card, loadExistingRelations]);
    
    // 处理表单字段变化
    const handleChange = useCallback((field, value) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    }, []);
    
    // 添加标签
    const handleAddTag = useCallback(() => {
        if (!tagInput.trim()) return;
        if (formData.tags.includes(tagInput.trim())) return;
        
        setFormData(prev => ({
            ...prev,
            tags: [...prev.tags, tagInput.trim()]
        }));
        setTagInput('');
    }, [tagInput, formData.tags]);
    
    // 删除标签
    const handleRemoveTag = useCallback((tagToRemove) => {
        setFormData(prev => ({
            ...prev,
            tags: prev.tags.filter(tag => tag !== tagToRemove)
        }));
    }, []);
    
    // 标签输入回车
    const handleTagKeyDown = useCallback((e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleAddTag();
        }
    }, [handleAddTag]);
    
    // AI 自动生成标签
    const handleAutoTag = useCallback(async () => {
        if (!formData.content.trim()) {
            alert('请先输入内容');
            return;
        }
        
        try {
            let tags;
            if (card) {
                tags = await autoTag(card.id);
            } else {
                // 新卡片，使用服务生成标签
                const response = await fetch('/api/v1/knowledge/auto-tag-preview', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: formData.content })
                });
                const data = await response.json();
                tags = data.tags;
            }
            
            if (tags && tags.length > 0) {
                setFormData(prev => ({
                    ...prev,
                    tags: [...new Set([...prev.tags, ...tags])]
                }));
            }
        } catch (err) {
            console.error('自动生成标签失败:', err);
            alert('自动生成标签失败');
        }
    }, [formData.content, card, autoTag]);
    
    // 发现关联
    const handleFindRelations = useCallback(async () => {
        if (!card) {
            alert('请先保存卡片');
            return;
        }
        
        try {
            const relations = await findRelations(card.id);
            setDiscoveredRelations(relations);
            setShowRelations(true);
        } catch (err) {
            console.error('发现关联失败:', err);
            alert('发现关联失败');
        }
    }, [card, findRelations]);
    
    // 添加关联
    const handleAddRelation = useCallback(async (targetCardId, relationType, description, confidence) => {
        if (!card) return;
        
        try {
            await createRelation(card.id, targetCardId, relationType, description, confidence);
            await loadExistingRelations(card.id);
            setDiscoveredRelations(prev => prev.filter(r => r.target_card_id !== targetCardId));
        } catch (err) {
            console.error('添加关联失败:', err);
            alert('添加关联失败');
        }
    }, [card, createRelation, loadExistingRelations]);
    
    // 删除关联
    const handleDeleteRelation = useCallback(async (relationId) => {
        if (!window.confirm('确定要删除这个关联吗？')) return;
        
        try {
            await deleteRelation(relationId);
            setExistingRelations(prev => prev.filter(r => r.id !== relationId));
        } catch (err) {
            console.error('删除关联失败:', err);
            alert('删除关联失败');
        }
    }, [deleteRelation]);
    
    // 保存卡片
    const handleSave = useCallback(async () => {
        if (!formData.title.trim()) {
            alert('请输入标题');
            return;
        }
        if (!formData.content.trim()) {
            alert('请输入内容');
            return;
        }
        
        try {
            if (isNew) {
                await createCard(formData);
            } else if (card) {
                await updateCard(card.id, formData);
            }
            onClose();
        } catch (err) {
            console.error('保存失败:', err);
            alert('保存失败: ' + (err.response?.data?.detail || err.message));
        }
    }, [formData, isNew, card, createCard, updateCard, onClose]);
    
    // 获取关联卡片信息
    const getCardInfo = useCallback((cardId) => {
        return cards.find(c => c.id === cardId);
    }, [cards]);
    
    // 获取论文标题
    const getPaperTitle = useCallback((paperId) => {
        const paper = papers.find(p => p.id === paperId);
        return paper ? paper.title : `论文 #${paperId}`;
    }, [papers]);
    
    return (
        <div className={styles.overlay} onClick={onClose}>
            <div className={styles.modal} onClick={e => e.stopPropagation()}>
                <header className={styles.header}>
                    <h2>{isNew ? '新建知识卡片' : '编辑知识卡片'}</h2>
                    <button className={styles.closeBtn} onClick={onClose}>×</button>
                </header>
                
                <div className={styles.body}>
                    {/* 标题 */}
                    <div className={styles.field}>
                        <label className={styles.label}>标题 *</label>
                        <input
                            type="text"
                            value={formData.title}
                            onChange={e => handleChange('title', e.target.value)}
                            placeholder="输入知识卡片标题"
                            className={styles.input}
                        />
                    </div>
                    
                    {/* 内容 */}
                    <div className={styles.field}>
                        <label className={styles.label}>内容 *</label>
                        <textarea
                            value={formData.content}
                            onChange={e => handleChange('content', e.target.value)}
                            placeholder="输入知识内容（支持 Markdown）"
                            className={styles.textarea}
                            rows={8}
                        />
                    </div>
                    
                    {/* 摘要 */}
                    <div className={styles.field}>
                        <label className={styles.label}>摘要</label>
                        <textarea
                            value={formData.summary}
                            onChange={e => handleChange('summary', e.target.value)}
                            placeholder="输入简要摘要（可选，留空将自动生成）"
                            className={styles.textarea}
                            rows={3}
                        />
                    </div>
                    
                    {/* 标签 */}
                    <div className={styles.field}>
                        <label className={styles.label}>
                            标签
                            <button 
                                type="button" 
                                onClick={handleAutoTag}
                                className={styles.aiBtn}
                                disabled={loading}
                            >
                                🤖 AI 生成
                            </button>
                        </label>
                        <div className={styles.tagInputBox}>
                            <div className={styles.tagList}>
                                {formData.tags.map(tag => (
                                    <span key={tag} className={styles.tag}>
                                        {tag}
                                        <button 
                                            type="button"
                                            onClick={() => handleRemoveTag(tag)}
                                            className={styles.tagRemove}
                                        >
                                            ×
                                        </button>
                                    </span>
                                ))}
                            </div>
                            <input
                                type="text"
                                value={tagInput}
                                onChange={e => setTagInput(e.target.value)}
                                onKeyDown={handleTagKeyDown}
                                placeholder="输入标签后按回车"
                                className={styles.tagInput}
                            />
                        </div>
                    </div>
                    
                    {/* 分类和来源 */}
                    <div className={styles.row}>
                        <div className={styles.field}>
                            <label className={styles.label}>分类</label>
                            <input
                                type="text"
                                value={formData.category}
                                onChange={e => handleChange('category', e.target.value)}
                                placeholder="输入分类"
                                className={styles.input}
                            />
                        </div>
                        
                        <div className={styles.field}>
                            <label className={styles.label}>来源类型</label>
                            <select
                                value={formData.source_type}
                                onChange={e => handleChange('source_type', e.target.value)}
                                className={styles.select}
                                disabled={!isNew && card?.source_type !== 'manual'}
                            >
                                {SOURCE_TYPES.map(type => (
                                    <option key={type.value} value={type.value}>
                                        {type.label}
                                    </option>
                                ))}
                            </select>
                        </div>
                    </div>
                    
                    {/* 关联论文 */}
                    {formData.source_type !== 'manual' && (
                        <div className={styles.field}>
                            <label className={styles.label}>关联论文</label>
                            {card?.paper_id ? (
                                <div className={styles.paperInfo}>
                                    📄 {getPaperTitle(card.paper_id)}
                                </div>
                            ) : (
                                <p className={styles.hint}>未关联论文</p>
                            )}
                        </div>
                    )}
                    
                    {/* 重要性 */}
                    <div className={styles.field}>
                        <label className={styles.label}>
                            重要性: {formData.importance.toFixed(1)}
                        </label>
                        <input
                            type="range"
                            min="0"
                            max="10"
                            step="0.5"
                            value={formData.importance}
                            onChange={e => handleChange('importance', parseFloat(e.target.value))}
                            className={styles.range}
                        />
                    </div>
                    
                    {/* 关联管理 */}
                    {!isNew && card && (
                        <div className={styles.relationsSection}>
                            <div className={styles.relationsHeader}>
                                <h3>🔗 知识关联</h3>
                                <button
                                    type="button"
                                    onClick={handleFindRelations}
                                    className={styles.aiBtn}
                                    disabled={loading}
                                >
                                    🤖 发现关联
                                </button>
                            </div>
                            
                            {/* 现有关联 */}
                            {existingRelations.length > 0 && (
                                <div className={styles.relationsList}>
                                    <h4>现有关联</h4>
                                    {existingRelations.map(relation => {
                                        const isSource = relation.source_card_id === card.id;
                                        const otherCardId = isSource ? relation.target_card_id : relation.source_card_id;
                                        const otherCard = getCardInfo(otherCardId);
                                        
                                        return (
                                            <div key={relation.id} className={styles.relationItem}>
                                                <span className={styles.relationDirection}>
                                                    {isSource ? '→' : '←'}
                                                </span>
                                                <span className={styles.relationType}>
                                                    {RELATION_TYPES.find(t => t.value === relation.relation_type)?.label || relation.relation_type}
                                                </span>
                                                <span className={styles.relationCard}>
                                                    {otherCard ? otherCard.title : `卡片 #${otherCardId}`}
                                                </span>
                                                <button
                                                    type="button"
                                                    onClick={() => handleDeleteRelation(relation.id)}
                                                    className={styles.relationDelete}
                                                >
                                                    ×
                                                </button>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                            
                            {/* 发现的关联 */}
                            {showRelations && discoveredRelations.length > 0 && (
                                <div className={styles.discoveredRelations}>
                                    <h4>发现的关联</h4>
                                    {discoveredRelations.map((relation, idx) => {
                                        const targetCard = getCardInfo(relation.target_card_id);
                                        
                                        return (
                                            <div key={idx} className={styles.discoveredItem}>
                                                <div className={styles.discoveredInfo}>
                                                    <span className={styles.relationType}>
                                                        {RELATION_TYPES.find(t => t.value === relation.relation_type)?.label || relation.relation_type}
                                                    </span>
                                                    <span className={styles.relationCard}>
                                                        {targetCard ? targetCard.title : `卡片 #${relation.target_card_id}`}
                                                    </span>
                                                    {relation.description && (
                                                        <span className={styles.relationDesc}>
                                                            {relation.description}
                                                        </span>
                                                    )}
                                                </div>
                                                <button
                                                    type="button"
                                                    onClick={() => handleAddRelation(
                                                        relation.target_card_id,
                                                        relation.relation_type,
                                                        relation.description,
                                                        relation.confidence
                                                    )}
                                                    className={styles.addRelationBtn}
                                                >
                                                    添加
                                                </button>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                            
                            {showRelations && discoveredRelations.length === 0 && (
                                <p className={styles.noRelations}>未发现新的关联</p>
                            )}
                        </div>
                    )}
                </div>
                
                <footer className={styles.footer}>
                    <button 
                        type="button" 
                        onClick={onClose}
                        className={styles.cancelBtn}
                    >
                        取消
                    </button>
                    <button 
                        type="button" 
                        onClick={handleSave}
                        className={styles.saveBtn}
                        disabled={loading}
                    >
                        {loading ? '保存中...' : '保存'}
                    </button>
                </footer>
            </div>
        </div>
    );
}

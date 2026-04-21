"""知识图谱构建服务

提供从论文文本中提取实体、构建关系、更新图谱的完整管道
"""
import json
import logging
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage
from sqlalchemy import select, func

from app.services.llm.llm_service import llm_service
from app.prompts.graph import EXTRACT_ENTITIES_PROMPT, BUILD_RELATIONS_PROMPT
from app.models.knowledge_graph import GraphNode, GraphEdge
from app.models.paper import Paper, PaperTextBlock

logger = logging.getLogger(__name__)


class GraphService:
    """知识图谱构建服务类"""

    async def extract_entities(self, paper_text: str) -> list[dict]:
        """使用 LLM 从论文文本中提取学术实体

        Args:
            paper_text: 论文文本内容

        Returns:
            实体列表，每项包含 name, type, description
            示例: [{"name": "Transformer", "type": "method", "description": "..."}]
        """
        # 截取前 3000 字符，避免超出 token 限制
        truncated_text = paper_text[:3000] if len(paper_text) > 3000 else paper_text

        messages = [
            SystemMessage(content="你是学术实体提取专家。只返回 JSON 数组，不要其他内容。"),
            HumanMessage(content=EXTRACT_ENTITIES_PROMPT.format(paper_text=truncated_text))
        ]

        try:
            response = await llm_service.llm.ainvoke(messages)
            content = response.content.strip()

            # 尝试解析 JSON
            entities = self._parse_json_response(content, default=[])

            # 验证实体格式
            valid_entities = []
            valid_types = {"concept", "method", "dataset", "metric", "author"}

            for entity in entities:
                if isinstance(entity, dict) and "name" in entity and "type" in entity:
                    # 规范化类型
                    entity_type = entity.get("type", "").lower().strip()
                    if entity_type in valid_types:
                        valid_entities.append({
                            "name": entity["name"].strip(),
                            "type": entity_type,
                            "description": entity.get("description", "")[:200]  # 限制描述长度
                        })

            logger.info(f"实体提取完成", extra={"entity_count": len(valid_entities)})
            return valid_entities

        except Exception as e:
            logger.error(f"实体提取失败: {e}", exc_info=True)
            return []

    async def match_entities(self, entities: list[dict], user_id: int, db) -> list[dict]:
        """匹配已有 GraphNode（名称模糊匹配），返回 matched/new 标记

        对已有节点更新 paper_ids；对新实体准备创建

        Args:
            entities: 待匹配的实体列表
            user_id: 用户 ID
            db: 数据库会话

        Returns:
            带匹配标记的实体列表，每项包含:
            - name, type, description
            - status: "matched" 或 "new"
            - node_id: 匹配到的节点 ID（status=matched 时）
        """
        if not entities:
            return []

        matched_entities = []

        for entity in entities:
            name = entity.get("name", "")
            if not name:
                continue

            # 使用 SQL LIKE 进行模糊匹配
            # 匹配策略：实体名称包含在已有节点名中，或已有节点名包含实体名称
            stmt = select(GraphNode).where(
                GraphNode.user_id == user_id,
                func.lower(GraphNode.name).like(f"%{name.lower()}%")
            )
            result = await db.execute(stmt)
            existing_node = result.scalar_one_or_none()

            if existing_node:
                # 找到匹配节点
                matched_entities.append({
                    "name": name,
                    "type": entity.get("type", "concept"),
                    "description": entity.get("description", ""),
                    "status": "matched",
                    "node_id": existing_node.id
                })
            else:
                # 新实体
                matched_entities.append({
                    "name": name,
                    "type": entity.get("type", "concept"),
                    "description": entity.get("description", ""),
                    "status": "new",
                    "node_id": None
                })

        logger.info(f"实体匹配完成", extra={
            "total": len(matched_entities),
            "matched": sum(1 for e in matched_entities if e["status"] == "matched"),
            "new": sum(1 for e in matched_entities if e["status"] == "new")
        })
        return matched_entities

    async def build_relations(self, entities: list[dict], paper_text: str) -> list[dict]:
        """使用 LLM 推断实体间关系

        Args:
            entities: 实体列表
            paper_text: 论文文本

        Returns:
            关系列表，每项包含 source, target, relation, evidence
            示例: [{"source": "Transformer", "target": "Self-Attention", "relation": "uses", "evidence": "..."}]
        """
        if len(entities) < 2:
            return []

        # 构建实体 JSON 用于 prompt
        entities_json = json.dumps([
            {"name": e["name"], "type": e["type"]}
            for e in entities
        ], ensure_ascii=False)

        # 截取前 2000 字符用于关系推断
        truncated_text = paper_text[:2000] if len(paper_text) > 2000 else paper_text

        messages = [
            SystemMessage(content="你是学术关系推断专家。只返回 JSON 数组，不要其他内容。"),
            HumanMessage(content=BUILD_RELATIONS_PROMPT.format(
                entities_json=entities_json,
                paper_text=truncated_text
            ))
        ]

        try:
            response = await llm_service.llm.ainvoke(messages)
            content = response.content.strip()

            # 尝试解析 JSON
            relations = self._parse_json_response(content, default=[])

            # 验证关系格式
            valid_relations = []
            valid_relation_types = {"uses", "improves", "contradicts", "extends", "evaluates_on"}
            entity_names = {e["name"] for e in entities}

            for relation in relations:
                if isinstance(relation, dict):
                    source = relation.get("source", "").strip()
                    target = relation.get("target", "").strip()
                    relation_type = relation.get("relation", "").lower().strip()

                    # 验证源和目标实体都存在
                    if source in entity_names and target in entity_names and relation_type in valid_relation_types:
                        valid_relations.append({
                            "source": source,
                            "target": target,
                            "relation": relation_type,
                            "evidence": relation.get("evidence", "")[:300]  # 限制证据长度
                        })

            logger.info(f"关系构建完成", extra={"relation_count": len(valid_relations)})
            return valid_relations

        except Exception as e:
            logger.error(f"关系构建失败: {e}", exc_info=True)
            return []

    async def update_graph(self, paper_id: int, user_id: int, db) -> dict:
        """完整的图谱更新管道

        执行流程：
        1. 获取论文文本（从 Paper 模型或 RAG 获取）
        2. extract_entities - 提取实体
        3. match_entities - 匹配已有节点（避免重复）
        4. build_relations - 构建关系
        5. 存储到 GraphNode/GraphEdge

        Args:
            paper_id: 论文 ID
            user_id: 用户 ID
            db: 数据库会话

        Returns:
            统计信息: {"nodes_added": N, "edges_added": M}
        """
        nodes_added = 0
        edges_added = 0

        try:
            # 1. 获取论文文本
            paper_text = await self._get_paper_text(paper_id, db)
            if not paper_text or len(paper_text) < 100:
                logger.warning(f"论文文本过短或不存在，跳过图谱更新", extra={"paper_id": paper_id})
                return {"nodes_added": 0, "edges_added": 0}

            # 2. 提取实体
            entities = await self.extract_entities(paper_text)
            if not entities:
                logger.warning(f"未提取到实体", extra={"paper_id": paper_id})
                return {"nodes_added": 0, "edges_added": 0}

            # 3. 匹配已有节点
            matched_entities = await self.match_entities(entities, user_id, db)

            # 4. 创建新节点 / 更新已有节点
            name_to_node_id = {}  # 用于后续关系构建

            for entity in matched_entities:
                if entity["status"] == "matched":
                    # 更新已有节点的 paper_ids
                    stmt = select(GraphNode).where(GraphNode.id == entity["node_id"])
                    result = await db.execute(stmt)
                    node = result.scalar_one_or_none()

                    if node:
                        # 添加当前论文 ID（如果不存在）
                        current_paper_ids = node.paper_ids or []
                        if paper_id not in current_paper_ids:
                            current_paper_ids.append(paper_id)
                            node.paper_ids = current_paper_ids

                        name_to_node_id[entity["name"]] = node.id

                else:
                    # 创建新节点
                    new_node = GraphNode(
                        name=entity["name"],
                        node_type=entity["type"],
                        description=entity["description"],
                        paper_ids=[paper_id],
                        user_id=user_id
                    )
                    db.add(new_node)
                    await db.flush()  # 获取新节点 ID

                    name_to_node_id[entity["name"]] = new_node.id
                    nodes_added += 1

            # 5. 构建关系
            relations = await self.build_relations(entities, paper_text)

            # 6. 存储关系
            for relation in relations:
                source_name = relation["source"]
                target_name = relation["target"]

                # 确保源和目标节点都已创建/匹配
                if source_name in name_to_node_id and target_name in name_to_node_id:
                    source_id = name_to_node_id[source_name]
                    target_id = name_to_node_id[target_name]

                    # 检查是否已存在相同关系（避免重复）
                    stmt = select(GraphEdge).where(
                        GraphEdge.source_id == source_id,
                        GraphEdge.target_id == target_id,
                        GraphEdge.relation_type == relation["relation"],
                        GraphEdge.paper_id == paper_id
                    )
                    result = await db.execute(stmt)
                    existing_edge = result.scalar_one_or_none()

                    if not existing_edge:
                        new_edge = GraphEdge(
                            source_id=source_id,
                            target_id=target_id,
                            relation_type=relation["relation"],
                            evidence=relation["evidence"],
                            paper_id=paper_id,
                            user_id=user_id
                        )
                        db.add(new_edge)
                        edges_added += 1

            await db.commit()

            logger.info(f"图谱更新完成", extra={
                "paper_id": paper_id,
                "nodes_added": nodes_added,
                "edges_added": edges_added
            })

            return {"nodes_added": nodes_added, "edges_added": edges_added}

        except Exception as e:
            await db.rollback()
            logger.error(f"图谱更新失败", extra={"paper_id": paper_id, "error": str(e)}, exc_info=True)
            raise

    async def _get_paper_text(self, paper_id: int, db) -> str:
        """获取论文文本

        优先从 PaperTextBlock 获取，如果没有则从 Paper 的 abstract 获取

        Args:
            paper_id: 论文 ID
            db: 数据库会话

        Returns:
            论文文本内容
        """
        # 尝试从 PaperTextBlock 获取
        stmt = select(PaperTextBlock).where(
            PaperTextBlock.paper_id == paper_id
        ).order_by(PaperTextBlock.page_number, PaperTextBlock.y0)

        result = await db.execute(stmt)
        text_blocks = result.scalars().all()

        if text_blocks:
            # 合并所有文本块
            texts = [block.text for block in text_blocks if block.text]
            return "\n".join(texts)

        # 如果没有文本块，尝试从 Paper 获取摘要
        stmt = select(Paper).where(Paper.id == paper_id)
        result = await db.execute(stmt)
        paper = result.scalar_one_or_none()

        if paper and paper.abstract:
            return paper.abstract

        return ""

    def _parse_json_response(self, content: str, default=None) -> any:
        """解析 LLM 返回的 JSON 响应

        处理可能的格式问题（如 markdown 代码块、多余文本等）

        Args:
            content: LLM 返回的文本内容
            default: 解析失败时的默认值

        Returns:
            解析后的 JSON 对象
        """
        if default is None:
            default = []

        try:
            # 尝试直接解析
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取 markdown 代码块中的 JSON
        try:
            # 查找 ```json ... ``` 或 ``` ... ``` 格式
            import re

            # 匹配 ```json 或 ``` 开头的代码块
            code_block_pattern = r'```(?:json)?\s*([\s\S]*?)```'
            matches = re.findall(code_block_pattern, content)

            for match in matches:
                try:
                    return json.loads(match.strip())
                except json.JSONDecodeError:
                    continue

            # 尝试查找方括号包裹的数组
            array_pattern = r'\[[\s\S]*\]'
            array_match = re.search(array_pattern, content)
            if array_match:
                try:
                    return json.loads(array_match.group())
                except json.JSONDecodeError:
                    pass

        except Exception:
            pass

        logger.warning(f"无法解析 JSON 响应", extra={"content_preview": content[:200]})
        return default


# 全局单例
graph_service = GraphService()

"""知识图谱服务模块"""
from app.services.knowledge.knowledge_service import KnowledgeService, knowledge_service
from app.services.knowledge.graph_service import GraphService, graph_service

__all__ = [
    "KnowledgeService", "knowledge_service",
    "GraphService", "graph_service",
]

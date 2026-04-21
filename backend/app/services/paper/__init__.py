"""论文处理服务模块"""
from app.services.paper.pdf_service import PDFService, pdf_service
from app.services.paper.batch_service import BatchService
from app.services.paper.recommendation_service import RecommendationService, recommendation_service

__all__ = [
    "PDFService", "pdf_service",
    "BatchService",
    "RecommendationService", "recommendation_service",
]

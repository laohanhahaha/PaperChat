"""PDF 处理服务（代理模块）

此模块已统一至 app.services.pdf_service。
保留此文件以维持既有 import 路径的兼容性。
"""
from app.services.pdf_service import PDFService, pdf_service

__all__ = ["PDFService", "pdf_service"]

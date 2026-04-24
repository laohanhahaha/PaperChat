"""PDF 图片提取服务烟雾测试

验证图片提取、图表检测及缓存机制的基本可用性。
"""
import os
import time

import pytest

from app.services.pdf_service import PDFService, pdf_service

# 使用项目自带的测试 PDF
TEST_PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "test.pdf")


@pytest.fixture(scope="module")
def test_pdf_path():
    path = os.path.abspath(TEST_PDF_PATH)
    if not os.path.exists(path):
        pytest.skip("测试 PDF 文件不存在")
    return path


class TestPDFImageExtraction:
    """PDF 图片提取测试"""

    @pytest.mark.asyncio
    async def test_extract_page_images(self, test_pdf_path):
        """验证单页图片提取返回列表结构"""
        images = await pdf_service.extract_page_images(test_pdf_path, page_num=0)

        assert isinstance(images, list)
        for img in images:
            assert "base64" in img
            assert "bbox" in img
            assert "type" in img
            assert "index" in img
            assert "width" in img
            assert "height" in img

    @pytest.mark.asyncio
    async def test_extract_all_images(self, test_pdf_path):
        """验证全文档图片提取返回列表并包含页码"""
        all_images = await pdf_service.extract_all_images(test_pdf_path)

        assert isinstance(all_images, list)
        for img in all_images:
            assert "page" in img
            assert isinstance(img["page"], int)

    @pytest.mark.asyncio
    async def test_detect_figures(self, test_pdf_path):
        """验证图表检测返回结构化结果"""
        figures = await pdf_service.detect_figures_and_tables(test_pdf_path, page_num=0)

        assert isinstance(figures, list)
        for fig in figures:
            assert "bbox" in fig
            assert "type" in fig
            assert fig["type"] in ("figure", "table")
            assert "label" in fig
            assert "page" in fig

    @pytest.mark.asyncio
    async def test_image_cache(self, test_pdf_path, tmp_path):
        """验证缓存机制：首次提取后缓存文件应存在，二次调用应更快命中"""
        # 使用临时目录避免污染真实缓存
        original_cache_dir = os.path.join("uploads", ".image_cache")

        # 先清理该页已有缓存（如果存在）
        cache_path = pdf_service._get_cache_path(test_pdf_path, 0)
        if os.path.exists(cache_path):
            os.remove(cache_path)

        # 首次调用
        t1 = time.perf_counter()
        images_first = await pdf_service.extract_page_images(test_pdf_path, page_num=0)
        t_first = time.perf_counter() - t1

        # 缓存文件应已生成
        assert os.path.exists(cache_path), "首次提取后缓存文件应存在"

        # 二次调用（应命中缓存）
        t2 = time.perf_counter()
        images_second = await pdf_service.extract_page_images(test_pdf_path, page_num=0)
        t_second = time.perf_counter() - t2

        # 验证缓存命中更快（通常 < 50ms）
        assert t_second < 0.05, f"缓存命中应快于 50ms，实际 {t_second * 1000:.1f}ms"

        # 两次结果应一致
        assert images_first == images_second

        # 清理
        if os.path.exists(cache_path):
            os.remove(cache_path)

"""多模态功能 单元测试 — 压缩/图表/批量分析"""
import base64
import io
import json
import sys
import os
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# test_compress_image
# ---------------------------------------------------------------------------
class TestCompressImage:
    """验证图片压缩逻辑"""

    @pytest.fixture
    def svc(self):
        from app.services.llm.llm_service import LLMService
        return LLMService()

    def _make_large_base64_image(self, width=2000, height=2000) -> str:
        """生成一张大尺寸带噪点的 PNG 图片并返回 base64 编码（保证压缩前 > 2MB）"""
        import numpy as np
        from PIL import Image

        # 随机噪点图片无法被 PNG 高效压缩，确保 > 2MB
        arr = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
        img = Image.fromarray(arr)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    def test_compress_reduces_size(self, svc):
        """压缩后 base64 字符串长度应显著小于原始"""
        large_b64 = self._make_large_base64_image()
        original_len = len(large_b64)
        compressed = svc._compress_image(large_b64, max_size_mb=2.0)
        assert len(compressed) < original_len

    def test_compress_result_under_2mb(self, svc):
        """压缩后解码的字节应 < 2MB"""
        large_b64 = self._make_large_base64_image()
        compressed = svc._compress_image(large_b64, max_size_mb=2.0)
        decoded = base64.b64decode(compressed)
        assert len(decoded) < 2 * 1024 * 1024

    def test_compress_returns_valid_base64(self, svc):
        """压缩结果应为合法 base64 字符串"""
        large_b64 = self._make_large_base64_image()
        compressed = svc._compress_image(large_b64, max_size_mb=2.0)
        # 不应抛出异常
        decoded = base64.b64decode(compressed)
        assert len(decoded) > 0

    def test_compress_small_image_unchanged(self, svc):
        """小图片不应被压缩（返回可能不同因格式转换，但解码大小应合理）"""
        from PIL import Image

        img = Image.new("RGB", (100, 100), color=(0, 0, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        small_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

        # 小图片本身不应触发压缩阈值
        # 但如果传入 _compress_image 也应正常返回
        result = svc._compress_image(small_b64, max_size_mb=10.0)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# test_analyze_chart
# ---------------------------------------------------------------------------
class TestAnalyzeChart:
    """验证 analyze_chart 方法"""

    @pytest.mark.asyncio
    async def test_analyze_chart_parses_json(self):
        """当 LLM 返回合法 JSON 时应正确解析"""
        from app.services.llm.llm_service import LLMService

        svc = LLMService()
        expected = {
            "chart_type": "bar",
            "data_summary": "销售额趋势",
            "key_findings": ["Q1 最高", "Q3 最低"],
            "raw_description": "柱状图展示季度销售额",
        }

        with patch.object(
            svc, "chat_with_image", new_callable=AsyncMock
        ) as mock_chat:
            mock_chat.return_value = json.dumps(expected, ensure_ascii=False)
            result = await svc.analyze_chart("fake_image_data")
            assert result["chart_type"] == "bar"
            assert len(result["key_findings"]) == 2

    @pytest.mark.asyncio
    async def test_analyze_chart_fallback_on_invalid_json(self):
        """当 LLM 返回非法 JSON 时应回退到 raw_description"""
        from app.services.llm.llm_service import LLMService

        svc = LLMService()

        with patch.object(
            svc, "chat_with_image", new_callable=AsyncMock
        ) as mock_chat:
            mock_chat.return_value = "这不是JSON，只是普通文本描述"
            result = await svc.analyze_chart("fake_image_data")
            assert result["chart_type"] == "unknown"
            assert result["raw_description"] == "这不是JSON，只是普通文本描述"


# ---------------------------------------------------------------------------
# test_batch_analyze_images
# ---------------------------------------------------------------------------
class TestBatchAnalyzeImages:
    """验证 batch_analyze_images 并行分析"""

    @pytest.mark.asyncio
    async def test_batch_returns_list(self):
        """批量分析应返回与输入等长的列表"""
        from app.services.llm.llm_service import LLMService

        svc = LLMService()
        images = [
            {"data": "img1"},
            {"data": "img2"},
            {"data": "img3"},
        ]

        with patch.object(
            svc, "chat_with_image", new_callable=AsyncMock
        ) as mock_chat:
            mock_chat.return_value = "描述"
            results = await svc.batch_analyze_images(images)
            assert len(results) == 3

    @pytest.mark.asyncio
    async def test_batch_handles_exception(self):
        """某张图片失败不应影响其他"""
        from app.services.llm.llm_service import LLMService

        svc = LLMService()
        images = [{"data": "img1"}, {"data": "img2"}]

        call_count = 0

        async def mock_fn(data, prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("test error")
            return "ok"

        with patch.object(
            svc, "chat_with_image", side_effect=mock_fn
        ):
            results = await svc.batch_analyze_images(images)
            assert len(results) == 2
            # 第一张失败应为异常对象
            assert isinstance(results[0], RuntimeError)
            # 第二张应正常
            assert results[1] == "ok"

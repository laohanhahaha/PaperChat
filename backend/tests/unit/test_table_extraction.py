"""表格结构化提取单元测试

验证 extract_table() 调用链：
- mock llm_service.chat_with_image
- 使用 AsyncMock 模拟异步方法
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.tools.base import ToolContext


class TestExtractTable:
    """llm_service.extract_table() 测试"""

    @pytest.fixture
    def service(self):
        from app.services.llm.llm_service import LLMService
        return LLMService()

    @pytest.mark.asyncio
    async def test_extract_table_returns_structured_result(self, service):
        """正常情况返回结构化表格数据"""
        mock_json = (
            '{"headers": ["Method", "PSNR"], "rows": [["Ours", "32.5"]], '
            '"markdown": "| Method | PSNR |\\n|---|---|\\n| Ours | 32.5 |", '
            '"csv": "Method,PSNR\\nOurs,32.5", "caption": "Results", '
            '"table_type": "results"}'
        )

        with patch.object(
            service, "chat_with_image", new_callable=AsyncMock, return_value=mock_json
        ):
            result = await service.extract_table("base64data")
            assert "headers" in result
            assert "rows" in result
            assert "markdown" in result
            assert isinstance(result["headers"], list)
            assert isinstance(result["rows"], list)

    @pytest.mark.asyncio
    async def test_extract_table_json_parse_fallback(self, service):
        """JSON 解析失败时的降级处理"""
        with patch.object(
            service,
            "chat_with_image",
            new_callable=AsyncMock,
            return_value="这是一个表格描述",
        ):
            result = await service.extract_table("base64data")
            assert "raw_text" in result or "markdown" in result

    @pytest.mark.asyncio
    async def test_extract_table_with_output_format(self, service):
        """不同输出格式参数"""
        mock_json = (
            '{"headers": ["A"], "rows": [["1"]], '
            '"markdown": "| A |", "csv": "A\\n1", '
            '"caption": "", "table_type": "other"}'
        )

        with patch.object(
            service, "chat_with_image", new_callable=AsyncMock, return_value=mock_json
        ):
            for fmt in ["markdown", "csv", "json"]:
                result = await service.extract_table("base64data", output_format=fmt)
                assert isinstance(result, dict)

"""LLM 客户端测试"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from habitica_forge.ai.llm_client import (
    LLMClient,
    LLMError,
    SmartDecomposeResult,
    _build_decompose_prompt,
)


class TestLLMClient:
    """LLM 客户端测试"""

    def test_init_with_defaults(self):
        """测试使用默认参数初始化"""
        with patch("habitica_forge.ai.llm_client.settings") as mock_settings:
            mock_settings.llm_api_key = "test-key"
            mock_settings.llm_base_url = "https://api.test.com/v1"
            mock_settings.llm_model = "test-model"

            client = LLMClient()
            assert client.api_key == "test-key"
            assert client.base_url == "https://api.test.com/v1"
            assert client.model == "test-model"

    def test_init_with_custom_params(self):
        """测试使用自定义参数初始化"""
        client = LLMClient(
            api_key="custom-key",
            base_url="https://custom.api.com/",
            model="custom-model",
            timeout=30.0,
        )
        assert client.api_key == "custom-key"
        assert client.base_url == "https://custom.api.com"  # 尾部斜杠被移除
        assert client.model == "custom-model"
        assert client.timeout == 30.0

    def test_get_headers(self):
        """测试请求头生成"""
        client = LLMClient(api_key="test-key")
        headers = client._get_headers()
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_chat_completion_success(self):
        """测试聊天完成请求成功"""
        client = LLMClient(api_key="test-key", base_url="https://api.test.com")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello, world!"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.chat_completion(
                messages=[{"role": "user", "content": "Hello"}]
            )
            assert result == "Hello, world!"

    @pytest.mark.asyncio
    async def test_chat_completion_json(self):
        """测试 JSON 响应解析"""
        client = LLMClient(api_key="test-key", base_url="https://api.test.com")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"key": "value"}'}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.chat_completion_json(
                messages=[{"role": "user", "content": "Test"}]
            )
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_chat_completion_json_with_markdown(self):
        """测试带 markdown 代码块的 JSON 响应解析"""
        client = LLMClient(api_key="test-key", base_url="https://api.test.com")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": '```json\n{"key": "value"}\n```'
                    }
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.chat_completion_json(
                messages=[{"role": "user", "content": "Test"}]
            )
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_chat_completion_json_with_model(self):
        """测试使用 Pydantic 模型解析响应"""
        client = LLMClient(api_key="test-key", base_url="https://api.test.com")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "task_title": "Test Task",
                            "task_notes": "Notes",
                            "suggested_priority": "easy",
                            "checklist": []
                        })
                    }
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(return_value=mock_response)
            mock_get_client.return_value = mock_http_client

            result = await client.chat_completion_json(
                messages=[{"role": "user", "content": "Test"}],
                response_model=SmartDecomposeResult,
            )
            assert isinstance(result, SmartDecomposeResult)
            assert result.task_title == "Test Task"
            assert result.suggested_priority == "easy"

    @pytest.mark.asyncio
    async def test_chat_completion_error(self):
        """测试请求错误处理"""
        client = LLMClient(api_key="test-key", base_url="https://api.test.com", max_retries=1)

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_http_client.post = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Error",
                    request=MagicMock(),
                    response=MagicMock(status_code=400, text="Bad Request"),
                )
            )
            mock_get_client.return_value = mock_http_client

            with pytest.raises(LLMError):
                await client.chat_completion(
                    messages=[{"role": "user", "content": "Test"}]
                )

    @pytest.mark.asyncio
    async def test_close(self):
        """测试关闭客户端"""
        client = LLMClient(api_key="test-key")

        mock_http_client = AsyncMock()
        mock_http_client.is_closed = False
        mock_http_client.aclose = AsyncMock()
        client._client = mock_http_client

        await client.close()
        mock_http_client.aclose.assert_called_once()
        assert client._client is None


class TestBuildDecomposePrompt:
    """测试 Prompt 构建"""

    def test_cyberpunk_style(self):
        """测试赛博朋克风格"""
        prompt = _build_decompose_prompt("cyberpunk")
        assert "赛博朋克" in prompt
        assert "霓虹灯" in prompt or "神经网络" in prompt

    def test_wuxia_style(self):
        """测试武侠风格"""
        prompt = _build_decompose_prompt("wuxia")
        assert "武侠" in prompt
        assert "江湖" in prompt or "修炼" in prompt

    def test_fantasy_style(self):
        """测试奇幻风格"""
        prompt = _build_decompose_prompt("fantasy")
        assert "奇幻" in prompt
        assert "魔法" in prompt or "龙" in prompt

    def test_normal_style(self):
        """测试正常风格"""
        prompt = _build_decompose_prompt("normal")
        assert "简洁" in prompt or "直接" in prompt

    def test_unknown_style_fallback(self):
        """测试未知风格回退到 normal"""
        prompt = _build_decompose_prompt("UnknownStyle")
        # 应该回退到 normal 风格
        assert "简洁" in prompt or "直接" in prompt

    def test_output_format(self):
        """测试输出格式要求"""
        prompt = _build_decompose_prompt("cyberpunk")
        assert "JSON" in prompt
        assert "task_title" in prompt
        assert "checklist" in prompt


class TestSmartDecomposeResult:
    """测试智能拆解结果模型"""

    def test_default_values(self):
        """测试默认值"""
        result = SmartDecomposeResult(task_title="Test")
        assert result.task_title == "Test"
        assert result.task_notes is None
        assert result.suggested_priority == "easy"
        assert result.checklist == []

    def test_with_checklist(self):
        """测试带子任务"""
        from habitica_forge.ai.llm_client import ChecklistSuggestion

        result = SmartDecomposeResult(
            task_title="Test Task",
            checklist=[
                ChecklistSuggestion(text="Step 1", priority="easy"),
                ChecklistSuggestion(text="Step 2", priority="medium"),
            ]
        )
        assert len(result.checklist) == 2
        assert result.checklist[0].text == "Step 1"
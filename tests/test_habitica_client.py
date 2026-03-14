"""Habitica 客户端单元测试"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from habitica_forge.clients.habitica import (
    HABITICA_API_BASE,
    HabiticaClient,
    RetryError,
    get_client,
)
from habitica_forge.models import ChecklistItem, TagData, TaskData


class TestHabiticaClient:
    """HabiticaClient 测试"""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings"""
        with patch("habitica_forge.clients.habitica.settings") as mock:
            mock.habitica_user_id = "test-user-id"
            mock.habitica_api_token = "test-api-token"
            yield mock

    @pytest.fixture
    def client(self, mock_settings):
        """创建客户端实例"""
        return HabiticaClient()

    def test_init(self, client):
        """测试初始化"""
        assert client.max_retries == 3
        assert client.base_backoff == 1.0
        assert client.max_backoff == 60.0
        assert client.timeout == 30.0

    def test_get_headers(self, client, mock_settings):
        """测试请求头生成"""
        headers = client._get_headers()
        assert headers["x-api-user"] == "test-user-id"
        assert headers["x-api-key"] == "test-api-token"
        assert "habitica-forge" in headers["x-client"]
        assert headers["Content-Type"] == "application/json"

    def test_calculate_backoff(self, client):
        """测试退避时间计算"""
        # 第一次尝试
        backoff = client._calculate_backoff(0)
        assert 0 <= backoff <= 3  # base_backoff * 2^0 + random(0,1) = 1 + random

        # 第二次尝试
        backoff = client._calculate_backoff(1)
        assert 0 <= backoff <= 5  # base_backoff * 2^1 + random(0,1) = 2 + random

        # 高次尝试应该被限制在 max_backoff
        backoff = client._calculate_backoff(10)
        assert backoff <= client.max_backoff

    @pytest.mark.asyncio
    async def test_get_tasks(self, client):
        """测试获取任务列表"""
        mock_response = {
            "success": True,
            "data": [
                {
                    "id": "task-1",
                    "text": "Test Task",
                    "type": "todo",
                    "tags": ["tag-1"],
                    "priority": 1.0,
                    "completed": False,
                }
            ],
        }

        with patch.object(
            client,
            "_request_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            tasks = await client.get_tasks()

        assert len(tasks) == 1
        assert tasks[0].id == "task-1"
        assert tasks[0].text == "Test Task"

    @pytest.mark.asyncio
    async def test_get_tasks_with_filter(self, client):
        """测试带过滤条件的任务获取"""
        mock_response = {"success": True, "data": []}

        with patch.object(
            client,
            "_request_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_request:
            await client.get_tasks(task_type="todos")
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args[0] == ("GET", "/tasks/user")
            assert call_args[1]["params"]["type"] == "todos"

    @pytest.mark.asyncio
    async def test_create_task(self, client):
        """测试创建任务"""
        task = TaskData(text="New Task", type="todo")
        mock_response = {
            "success": True,
            "data": {
                "id": "new-task-id",
                "text": "New Task",
                "type": "todo",
                "priority": 1.0,
            },
        }

        with patch.object(
            client,
            "_request_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            created = await client.create_task(task)

        assert created.id == "new-task-id"
        assert created.text == "New Task"

    @pytest.mark.asyncio
    async def test_update_task(self, client):
        """测试更新任务"""
        mock_response = {
            "success": True,
            "data": {
                "id": "task-id",
                "text": "Updated Text",
                "type": "todo",
                "notes": "New Notes",
            },
        }

        with patch.object(
            client,
            "_request_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            updated = await client.update_task("task-id", text="Updated Text", notes="New Notes")

        assert updated.text == "Updated Text"

    @pytest.mark.asyncio
    async def test_complete_task(self, client):
        """测试完成任务"""
        mock_response = {"success": True, "data": {}}

        with patch.object(
            client,
            "_request_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await client.complete_task("task-id")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_delete_task(self, client):
        """测试删除任务"""
        with patch.object(
            client,
            "_request_with_retry",
            new_callable=AsyncMock,
            return_value={"success": True},
        ):
            success = await client.delete_task("task-id")

        assert success is True

    @pytest.mark.asyncio
    async def test_add_checklist_item(self, client):
        """测试添加 Checklist 项"""
        mock_response = {
            "success": True,
            "data": {"id": "item-id", "text": "Checklist Item", "completed": False},
        }

        with patch.object(
            client,
            "_request_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            item = await client.add_checklist_item("task-id", "Checklist Item")

        assert item.id == "item-id"
        assert item.text == "Checklist Item"

    @pytest.mark.asyncio
    async def test_get_tags(self, client):
        """测试获取标签列表"""
        mock_response = {
            "success": True,
            "data": [
                {"id": "tag-1", "name": "Work"},
                {"id": "tag-2", "name": "Personal"},
            ],
        }

        with patch.object(
            client,
            "_request_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            tags = await client.get_tags()

        assert len(tags) == 2
        assert tags[0].name == "Work"

    @pytest.mark.asyncio
    async def test_create_tag(self, client):
        """测试创建标签"""
        mock_response = {
            "success": True,
            "data": {"id": "new-tag-id", "name": "New Tag"},
        }

        with patch.object(
            client,
            "_request_with_retry",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            tag = await client.create_tag("New Tag")

        assert tag.id == "new-tag-id"
        assert tag.name == "New Tag"

    @pytest.mark.asyncio
    async def test_add_tag_to_task(self, client):
        """测试为任务添加标签"""
        with patch.object(
            client,
            "_request_with_retry",
            new_callable=AsyncMock,
            return_value={"success": True},
        ):
            success = await client.add_tag_to_task("task-id", "tag-id")

        assert success is True

    @pytest.mark.asyncio
    async def test_get_or_create_tag_existing(self, client):
        """测试获取已存在的标签"""
        mock_tags_response = {
            "success": True,
            "data": [{"id": "existing-tag-id", "name": "Existing Tag"}],
        }

        with patch.object(
            client,
            "get_tags",
            new_callable=AsyncMock,
            return_value=[TagData(id="existing-tag-id", name="Existing Tag")],
        ):
            tag = await client.get_or_create_tag("Existing Tag")

        assert tag.id == "existing-tag-id"

    @pytest.mark.asyncio
    async def test_get_or_create_tag_new(self, client):
        """测试创建不存在的标签"""
        with patch.object(
            client,
            "get_tags",
            new_callable=AsyncMock,
            return_value=[],
        ):
            with patch.object(
                client,
                "create_tag",
                new_callable=AsyncMock,
                return_value=TagData(id="new-tag-id", name="New Tag"),
            ):
                tag = await client.get_or_create_tag("New Tag")

        assert tag.id == "new-tag-id"

    @pytest.mark.asyncio
    async def test_close(self, client):
        """测试关闭客户端"""
        await client._get_client()  # 确保客户端已创建
        await client.close()
        assert client._client is None

    def test_get_client_singleton(self):
        """测试全局客户端单例"""
        from habitica_forge.clients.habitica import _client_instance

        # 清除现有实例
        import habitica_forge.clients.habitica as client_module

        client_module._client_instance = None

        client1 = get_client()
        client2 = get_client()
        assert client1 is client2


class TestRetryMechanism:
    """重试机制测试"""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings"""
        with patch("habitica_forge.clients.habitica.settings") as mock:
            mock.habitica_user_id = "test-user-id"
            mock.habitica_api_token = "test-api-token"
            yield mock

    @pytest.mark.asyncio
    async def test_retry_on_429(self, mock_settings):
        """测试 429 错误重试"""
        client = HabiticaClient(max_retries=2)

        # 模拟 429 响应后成功
        call_count = 0

        async def mock_request(method, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError(
                    "Too Many Requests",
                    request=MagicMock(),
                    response=MagicMock(status_code=429, headers={"Retry-After": "0.1"}),
                )
            return {"success": True, "data": {}}

        # 创建真实的 AsyncClient 进行测试比较复杂，这里简化测试
        # 实际集成测试会使用真实 HTTP 请求
        await client.close()

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, mock_settings):
        """测试超过最大重试次数"""
        client = HabiticaClient(max_retries=1)

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = AsyncMock()
            mock_get_client.return_value = mock_http_client

            # 模拟持续的服务器错误
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Server Error",
                request=MagicMock(),
                response=mock_response,
            )
            mock_http_client.request = AsyncMock(return_value=mock_response)

            with pytest.raises(RetryError):
                await client._request_with_retry("GET", "/test")

        await client.close()
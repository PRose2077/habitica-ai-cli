"""TaskService 测试模块。

测试创建任务、获取任务、完成任务等功能。
使用 pytest-mock 来模拟 HTTP 请求，避免实际调用 Habitica API。
"""

import os
import sys
from datetime import datetime
from typing import List
from unittest.mock import Mock, patch

import pytest
from pydantic import TypeAdapter

# Ensure `src` is importable
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from model.client import HabiticaClient
from model.models import Task, TaskType, Todo, Habit
from services.task import TaskService


@pytest.fixture
def mock_env_vars(monkeypatch):
    """设置测试用的环境变量。"""
    monkeypatch.setenv("HABITICA_USER_ID", "test-user-id")
    monkeypatch.setenv("HABITICA_API_TOKEN", "test-api-token")


@pytest.fixture
def client(mock_env_vars):
    """创建 HabiticaClient 实例。"""
    return HabiticaClient()


@pytest.fixture
def task_service(client):
    """创建 TaskService 实例。"""
    return TaskService(client)


class TestFetchTasks:
    """测试获取任务功能。"""

    def test_fetch_all_tasks_success(self, task_service):
        """测试成功获取所有任务。"""
        # 模拟 API 响应数据
        mock_response_data = {
            "data": [
                {
                    "_id": "todo-1",
                    "type": "todo",
                    "text": "测试待办任务",
                    "notes": "这是一个测试",
                    "priority": 1.5,
                    "completed": False,
                    "checklist": [],
                },
                {
                    "_id": "habit-1",
                    "type": "habit",
                    "text": "测试习惯",
                    "notes": "",
                    "priority": 1.0,
                    "up": True,
                    "down": False,
                    "counterUp": 5,
                    "counterDown": 0,
                },
            ]
        }

        with patch("services.task.create_task.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            tasks = task_service.fetch_tasks()

            assert len(tasks) == 2
            # 使用 type 字段验证任务类型
            assert tasks[0].type == "todo"
            assert tasks[0].text == "测试待办任务"
            assert tasks[1].type == "habit"
            assert tasks[1].text == "测试习惯"

            # 验证请求参数
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert call_args[0][0] == "https://habitica.com/api/v3/tasks/user"
            assert call_args[1]["params"] == {}

    def test_fetch_tasks_by_type(self, task_service):
        """测试按类型获取任务。"""
        mock_response_data = {
            "data": [
                {
                    "_id": "todo-1",
                    "type": "todo",
                    "text": "测试待办",
                    "completed": False,
                }
            ]
        }

        with patch("services.task.create_task.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            tasks = task_service.fetch_tasks(task_type=TaskType.TODO)

            assert len(tasks) == 1
            assert tasks[0].type == "todo"

            # 验证请求参数包含类型过滤
            call_args = mock_get.call_args
            assert call_args[1]["params"] == {"type": "todo"}

    def test_fetch_tasks_empty_response(self, task_service):
        """测试获取空任务列表。"""
        mock_response_data = {"data": []}

        with patch("services.task.create_task.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            tasks = task_service.fetch_tasks()

            assert tasks == []

    def test_fetch_tasks_api_error(self, task_service):
        """测试 API 错误处理。"""
        with patch("services.task.create_task.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = Exception("API Error")
            mock_get.return_value = mock_response

            with pytest.raises(Exception, match="API Error"):
                task_service.fetch_tasks()


class TestScoreTask:
    """测试完成任务功能。"""

    def test_score_task_up_success(self, task_service):
        """测试正向完成任务。"""
        mock_response_data = {
            "data": {
                "delta": 1.5,
                "gp": 100.5,
                "hp": 50,
                "exp": 150,
                "mp": 50,
                "lvl": 10,
            }
        }

        with patch("services.task.create_task.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            result = task_service.score_task("task-123", direction="up")

            assert result["data"]["delta"] == 1.5
            assert result["data"]["gp"] == 100.5

            # 验证请求 URL
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://habitica.com/api/v3/tasks/task-123/score/up"

    def test_score_task_down_success(self, task_service):
        """测试负向完成任务。"""
        mock_response_data = {"data": {"delta": -1.0}}

        with patch("services.task.create_task.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            result = task_service.score_task("task-456", direction="down")

            assert result["data"]["delta"] == -1.0

            call_args = mock_post.call_args
            assert call_args[0][0] == "https://habitica.com/api/v3/tasks/task-456/score/down"

    def test_score_task_default_direction(self, task_service):
        """测试默认方向为 up。"""
        mock_response_data = {"data": {"delta": 1.0}}

        with patch("services.task.create_task.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_post.return_value = mock_response

            result = task_service.score_task("task-789")

            call_args = mock_post.call_args
            assert call_args[0][0] == "https://habitica.com/api/v3/tasks/task-789/score/up"

    def test_score_task_api_error(self, task_service):
        """测试 API 错误处理。"""
        with patch("services.task.create_task.requests.post") as mock_post:
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = Exception("Task not found")
            mock_post.return_value = mock_response

            with pytest.raises(Exception, match="Task not found"):
                task_service.score_task("invalid-task-id")


class TestCreateTask:
    """测试创建任务功能。"""

    def test_create_task_success(self, task_service):
        """测试通过 TaskService 创建任务成功。"""
        mock_response_data = {
            "data": {
                "_id": "todo-created-1",
                "type": "todo",
                "text": "重构连接池",
                "notes": "拆解后的执行任务",
                "priority": 2.0,
            }
        }

        with patch("model.client.requests.request") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            result = task_service.create_task(
                text="重构连接池",
                task_type=TaskType.TODO,
                notes="拆解后的执行任务",
                priority=2.0,
            )

            assert result["data"]["text"] == "重构连接池"
            mock_request.assert_called_once()

            call_args = mock_request.call_args
            assert call_args[0][0] == "POST"
            assert call_args[0][1] == "https://habitica.com/api/v3/tasks/user"
            assert call_args[1]["json"]["type"] == "todo"
            assert call_args[1]["json"]["text"] == "重构连接池"

    def test_create_task_with_optional_fields(self, task_service):
        """测试创建任务时携带日期和子任务。"""
        with patch("model.client.requests.request") as mock_request:
            mock_response = Mock()
            mock_response.json.return_value = {"data": {"_id": "todo-created-2"}}
            mock_response.raise_for_status = Mock()
            mock_request.return_value = mock_response

            task_service.create_task(
                text="写周报",
                task_type="todo",
                date="2026-03-31",
                checklist=[{"text": "整理本周进展"}],
            )

            payload = mock_request.call_args[1]["json"]
            assert payload["date"] == "2026-03-31"
            assert payload["checklist"] == [{"text": "整理本周进展"}]


class TestTaskServiceIntegration:
    """集成测试：验证 TaskService 与 HabiticaClient 的协作。"""

    def test_headers_passed_correctly(self, task_service, client):
        """测试请求头正确传递。"""
        mock_response_data = {"data": []}

        with patch("services.task.create_task.requests.get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            task_service.fetch_tasks()

            call_args = mock_get.call_args
            headers = call_args[1]["headers"]

            assert headers["x-api-user"] == "test-user-id"
            assert headers["x-api-key"] == "test-api-token"
            assert headers["Content-Type"] == "application/json"
            assert "test-user-id-habitica-ai" in headers["x-client"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

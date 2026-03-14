"""CLI 命令测试"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from habitica_forge.cli.main import app
from habitica_forge.models import ChecklistItem, TagData, TaskData

runner = CliRunner()


# ============================================
# Fixtures
# ============================================


@pytest.fixture(autouse=True)
def mock_settings():
    """自动 mock settings"""
    with patch("habitica_forge.core.config.get_settings") as mock:
        settings = MagicMock()
        settings.habitica_user_id = "test-user-id"
        settings.habitica_api_token = "test-api-token"
        settings.llm_api_key = "test-llm-key"
        settings.llm_base_url = "https://api.test.com/v1"
        settings.llm_model = "test-model"
        settings.log_level = "INFO"
        settings.forge_style = "Cyberpunk"
        mock.return_value = settings
        yield settings


@pytest.fixture
def mock_habitica_client():
    """创建 mock HabiticaClient"""
    with patch("habitica_forge.cli.main.HabiticaClient") as mock_client_class:
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        mock_client_class.return_value = client
        yield client


@pytest.fixture
def mock_cache_manager():
    """创建 mock CacheManager"""
    with patch("habitica_forge.core.cache.get_cache_manager") as mock:
        cache = MagicMock()
        cache.tasks = MagicMock()
        cache.tags = MagicMock()
        cache.tags.get_tags.return_value = []  # 默认返回空列表
        cache.index = MagicMock()
        cache.index.get_uuid.return_value = None
        cache.index.get_checklist_item_id.return_value = None
        cache.index.get_title_mapping.return_value = None
        mock.return_value = cache
        yield cache


# ============================================
# 基础命令测试
# ============================================


class TestBasicCommands:
    """基础命令测试"""

    def test_version(self, mock_settings):
        """测试版本命令"""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        # 版本号被 Rich 渲染，检查核心内容
        assert "version" in result.output.lower()

    def test_help(self, mock_settings):
        """测试帮助命令"""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "forge" in result.output.lower()


# ============================================
# list 命令测试
# ============================================


class TestListCommand:
    """list 命令测试"""

    def test_list_todos(self, mock_habitica_client, mock_settings):
        """测试列出待办任务"""
        mock_habitica_client.get_tasks.return_value = [
            TaskData(
                id="task-123-abc",
                text="Test Task 1",
                type="todo",
                priority=1.0,
                completed=False,
            ),
            TaskData(
                id="task-456-def",
                text="Test Task 2",
                type="todo",
                priority=2.0,
                completed=False,
            ),
        ]
        mock_habitica_client.get_tags.return_value = [
            TagData(id="tag-1", name="Work"),
        ]

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0

    def test_list_empty(self, mock_habitica_client, mock_settings):
        """测试空任务列表"""
        mock_habitica_client.get_tasks.return_value = []
        mock_habitica_client.get_tags.return_value = []

        result = runner.invoke(app, ["list"])

        assert result.exit_code == 0


# ============================================
# add 命令测试
# ============================================


class TestAddCommand:
    """add 命令测试"""

    def test_add_task(self, mock_habitica_client, mock_cache_manager, mock_settings):
        """测试添加任务"""
        mock_habitica_client.create_task.return_value = TaskData(
            id="new-task-id",
            text="New Test Task",
            type="todo",
            priority=1.0,
        )
        mock_habitica_client.get_or_create_tag = AsyncMock(
            return_value=TagData(id="tag-1", name="Test")
        )

        result = runner.invoke(app, ["add", "New Test Task"])

        assert result.exit_code == 0


# ============================================
# show 命令测试
# ============================================


class TestShowCommand:
    """show 命令测试"""

    def test_show_task(self, mock_habitica_client, mock_settings):
        """测试显示任务详情"""
        mock_habitica_client.get_task.return_value = TaskData(
            id="task-123",
            text="Detailed Task",
            type="todo",
            priority=1.5,
            notes="This is a note",
            completed=False,
        )
        mock_habitica_client.get_tags.return_value = []

        result = runner.invoke(app, ["show", "task-123"])

        assert result.exit_code == 0
        assert "Detailed Task" in result.output


# ============================================
# done 命令测试
# ============================================


class TestDoneCommand:
    """done 命令测试"""

    def test_complete_task(self, mock_habitica_client, mock_cache_manager, mock_settings):
        """测试完成任务"""
        mock_habitica_client.get_task.return_value = TaskData(
            id="task-123",
            text="Task to complete",
            type="todo",
            priority=1.0,
        )
        mock_habitica_client.complete_task.return_value = {"success": True}

        result = runner.invoke(app, ["done", "task-123"])

        assert result.exit_code == 0


# ============================================
# sync 命令测试
# ============================================


class TestSyncCommand:
    """sync 命令测试"""

    def test_sync(self, mock_habitica_client, mock_cache_manager, mock_settings):
        """测试同步命令"""
        mock_habitica_client.get_tasks.return_value = [
            TaskData(id="t1", text="Task 1", type="todo", priority=1.0),
            TaskData(id="t2", text="Task 2", type="todo", priority=1.0),
        ]
        mock_habitica_client.get_tags.return_value = [
            TagData(id="tag1", name="Work"),
        ]

        result = runner.invoke(app, ["sync"])

        assert result.exit_code == 0


# ============================================
# 子任务命令测试
# ============================================


class TestSubtaskCommands:
    """子任务命令测试"""

    def test_sub_add(self, mock_habitica_client, mock_cache_manager, mock_settings):
        """测试添加子任务"""
        mock_habitica_client.add_checklist_item.return_value = ChecklistItem(
            id="item-1",
            text="New subtask",
            completed=False,
        )

        result = runner.invoke(app, ["sub-add", "task-123", "New subtask"])

        assert result.exit_code == 0

    def test_sub_done(self, mock_habitica_client, mock_cache_manager, mock_settings):
        """测试完成子任务"""
        mock_habitica_client.complete_checklist_item.return_value = MagicMock()

        result = runner.invoke(app, ["sub-done", "task-123", "item-1"])

        assert result.exit_code == 0


# ============================================
# Viewer 函数测试
# ============================================


class TestViewerFunctions:
    """Viewer 函数测试"""

    def test_format_date_today(self):
        """测试今天的日期格式化"""
        from habitica_forge.cli.viewer import format_date

        now = datetime.now(timezone.utc)
        result = format_date(now)
        assert "今天" in result

    def test_format_date_tomorrow(self):
        """测试明天的日期格式化"""
        from habitica_forge.cli.viewer import format_date

        now = datetime.now(timezone.utc)
        tomorrow = now + timedelta(days=1)
        result = format_date(tomorrow)
        assert "明天" in result

    def test_format_date_past(self):
        """测试过去的日期格式化"""
        from habitica_forge.cli.viewer import format_date

        now = datetime.now(timezone.utc)
        past = now - timedelta(days=1)
        result = format_date(past)
        assert "[red]" in result

    def test_format_date_future(self):
        """测试未来的日期格式化"""
        from habitica_forge.cli.viewer import format_date

        now = datetime.now(timezone.utc)
        future = now + timedelta(days=5)
        result = format_date(future)
        assert "5天后" in result

    def test_format_date_none(self):
        """测试空日期"""
        from habitica_forge.cli.viewer import format_date

        assert format_date(None) == ""

    def test_truncate_text(self):
        """测试文本截断"""
        from habitica_forge.cli.viewer import truncate_text

        short_text = "短文本"
        assert truncate_text(short_text) == short_text

        long_text = "这是一个非常长的文本需要被截断处理" * 10
        result = truncate_text(long_text, max_length=20)
        assert len(result) <= 23
        assert result.endswith("...")

    def test_render_checklist_progress(self):
        """测试 Checklist 进度渲染"""
        from habitica_forge.cli.viewer import render_checklist_progress

        assert render_checklist_progress([]) == ""

        items = [
            ChecklistItem(text="a", completed=True),
            ChecklistItem(text="b", completed=True),
        ]
        result = render_checklist_progress(items, completed=True)
        assert "100%" in result

        items = [
            ChecklistItem(text="a", completed=True),
            ChecklistItem(text="b", completed=False),
        ]
        result = render_checklist_progress(items)
        assert "1/2" in result

    def test_get_priority_label(self):
        """测试优先级标签"""
        from habitica_forge.cli.viewer import get_priority_label

        label, style = get_priority_label(0.1)
        assert "trivial" in label.lower()

        label, style = get_priority_label(1.0)
        assert "easy" in label.lower()

        label, style = get_priority_label(1.5)
        assert "medium" in label.lower()

        label, style = get_priority_label(2.0)
        assert "hard" in label.lower()

    def test_get_current_title(self):
        """测试获取当前佩戴称号"""
        from habitica_forge.cli.header import get_current_identity

        # 测试没有称号的情况
        title, valid = get_current_identity()
        assert title is None  # 没有缓存时应该返回 None
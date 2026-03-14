"""智能拆解命令测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from habitica_forge.ai.llm_client import ChecklistSuggestion, SmartDecomposeResult
from habitica_forge.cli.smart import (
    PRIORITY_MAP,
    _create_task_with_decomposition,
    _decompose_task,
    _render_decompose_result,
    _resolve_task_id,
    _update_task_with_decomposition,
)
from habitica_forge.models import ChecklistItem, TaskData


class TestResolveTaskId:
    """测试任务 ID 解析"""

    def test_long_id_returns_as_is(self):
        """测试长 ID 直接返回"""
        result = _resolve_task_id("abc12345def67890")
        assert result == "abc12345def67890"

    def test_short_id_looks_up_cache(self):
        """测试短编号从缓存查找"""
        with patch("habitica_forge.cli.smart.get_cache_manager") as mock_cache:
            mock_index = MagicMock()
            mock_index.get_uuid.return_value = "full-uuid-12345"
            mock_cache.return_value.index = mock_index

            result = _resolve_task_id("1")
            assert result == "full-uuid-12345"

    def test_short_id_not_found_returns_as_is(self):
        """测试短编号找不到时返回原值"""
        with patch("habitica_forge.cli.smart.get_cache_manager") as mock_cache:
            mock_index = MagicMock()
            mock_index.get_uuid.return_value = None
            mock_cache.return_value.index = mock_index

            result = _resolve_task_id("999")
            assert result == "999"


class TestPriorityMap:
    """测试优先级映射"""

    def test_all_priorities_mapped(self):
        """测试所有优先级都有映射"""
        assert "trivial" in PRIORITY_MAP
        assert "easy" in PRIORITY_MAP
        assert "medium" in PRIORITY_MAP
        assert "hard" in PRIORITY_MAP

    def test_priority_values(self):
        """测试优先级值正确"""
        assert PRIORITY_MAP["trivial"] == 0.1
        assert PRIORITY_MAP["easy"] == 1.0
        assert PRIORITY_MAP["medium"] == 1.5
        assert PRIORITY_MAP["hard"] == 2.0


class TestDecomposeTask:
    """测试任务拆解"""

    @pytest.mark.asyncio
    async def test_decompose_task_basic(self):
        """测试基本拆解"""
        mock_result = SmartDecomposeResult(
            task_title="Optimized Task",
            checklist=[
                ChecklistSuggestion(text="Step 1"),
                ChecklistSuggestion(text="Step 2"),
            ]
        )

        with patch("habitica_forge.cli.smart.LLMClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.smart_decompose = AsyncMock(return_value=mock_result)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            MockClient.return_value = mock_client

            result = await _decompose_task("Original Task")

            assert result.task_title == "Optimized Task"
            assert len(result.checklist) == 2

    @pytest.mark.asyncio
    async def test_decompose_task_with_existing_checklist(self):
        """测试带现有子任务拆解"""
        mock_result = SmartDecomposeResult(
            task_title="Task",
            checklist=[ChecklistSuggestion(text="New Step")]
        )

        with patch("habitica_forge.cli.smart.LLMClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.smart_decompose = AsyncMock(return_value=mock_result)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            MockClient.return_value = mock_client

            result = await _decompose_task(
                task_text="Task",
                existing_checklist=["Old Step 1", "Old Step 2"]
            )

            # 验证传入了现有 checklist
            call_args = mock_client.smart_decompose.call_args
            assert call_args.kwargs["existing_checklist"] == ["Old Step 1", "Old Step 2"]


class TestCreateTaskWithDecomposition:
    """测试创建任务"""

    @pytest.mark.asyncio
    async def test_create_task_basic(self):
        """测试基本创建"""
        result = SmartDecomposeResult(
            task_title="New Task",
            task_notes="Task notes",
            suggested_priority="medium",
            checklist=[
                ChecklistSuggestion(text="Step 1", priority="easy"),
                ChecklistSuggestion(text="Step 2", priority="hard"),
            ]
        )

        mock_client = AsyncMock()
        mock_client.create_task = AsyncMock(
            return_value=TaskData(id="new-task-id", text="New Task", type="todo")
        )

        created = await _create_task_with_decomposition(mock_client, result)

        # 验证调用参数
        call_args = mock_client.create_task.call_args
        task_arg = call_args.args[0]

        assert task_arg.text == "New Task"
        assert task_arg.notes == "Task notes"
        assert task_arg.priority == 1.5  # medium
        assert len(task_arg.checklist) == 2

    @pytest.mark.asyncio
    async def test_create_task_no_checklist(self):
        """测试无子任务创建"""
        result = SmartDecomposeResult(
            task_title="Simple Task",
            checklist=[]
        )

        mock_client = AsyncMock()
        mock_client.create_task = AsyncMock(
            return_value=TaskData(id="simple-id", text="Simple Task", type="todo")
        )

        created = await _create_task_with_decomposition(mock_client, result)

        call_args = mock_client.create_task.call_args
        task_arg = call_args.args[0]
        assert task_arg.checklist == []


class TestUpdateTaskWithDecomposition:
    """测试更新任务"""

    @pytest.mark.asyncio
    async def test_update_task_all_fields(self):
        """测试更新所有字段"""
        result = SmartDecomposeResult(
            task_title="Updated Title",
            task_notes="New notes",
            suggested_priority="hard",
            checklist=[ChecklistSuggestion(text="New Step")]
        )

        existing = TaskData(
            id="task-id",
            text="Old Title",
            type="todo",
            notes="Old notes",
            priority=1.0,
            checklist=[ChecklistItem(text="Old Step")]
        )

        mock_client = AsyncMock()
        mock_client.update_task = AsyncMock(
            return_value=TaskData(id="task-id", text="Updated Title", type="todo")
        )

        updated = await _update_task_with_decomposition(
            mock_client, "task-id", result, existing
        )

        # 验证更新调用
        call_args = mock_client.update_task.call_args
        assert call_args.args[0] == "task-id"
        updates = call_args.kwargs

        assert updates["text"] == "Updated Title"
        assert updates["notes"] == "New notes"
        assert updates["priority"] == 2.0  # hard
        assert len(updates["checklist"]) == 1

    @pytest.mark.asyncio
    async def test_update_task_no_changes(self):
        """测试无变更时不更新"""
        result = SmartDecomposeResult(
            task_title="Same Title",
            suggested_priority="easy",
            checklist=[]
        )

        existing = TaskData(
            id="task-id",
            text="Same Title",
            type="todo",
            priority=1.0,
            checklist=[]
        )

        mock_client = AsyncMock()

        updated = await _update_task_with_decomposition(
            mock_client, "task-id", result, existing
        )

        # 不应该调用 update_task
        mock_client.update_task.assert_not_called()
        # 返回原任务
        assert updated == existing


class TestRenderDecomposeResult:
    """测试结果渲染"""

    def test_render_basic(self, capsys):
        """测试基本渲染"""
        result = SmartDecomposeResult(
            task_title="Test Task",
            task_notes="Notes here",
            suggested_priority="medium",
            checklist=[
                ChecklistSuggestion(text="Step 1", priority="easy"),
                ChecklistSuggestion(text="Step 2", priority="hard"),
            ]
        )

        _render_decompose_result(result)

        # 验证输出包含关键信息（Rich 会插入 ANSI 代码）
        captured = capsys.readouterr()
        output = captured.out

        # 使用 strip 去除 ANSI 颜色代码后的检查
        # Rich 的 console.print 输出在 capsys 中会有 ANSI 转义序列
        assert "Test Task" in output
        assert "Notes here" in output
        assert "medium" in output
        # "Step" 被拆分到多个部分，检查核心内容
        assert "Step" in output

    def test_render_no_checklist(self, capsys):
        """测试无子任务渲染"""
        result = SmartDecomposeResult(
            task_title="Simple Task",
            checklist=[]
        )

        _render_decompose_result(result)

        captured = capsys.readouterr()
        output = captured.out

        assert "Simple Task" in output
        assert "无需拆解" in output or "no" in output.lower() or len(output) > 0


class TestSmartDecomposeResult:
    """测试 SmartDecomposeResult 模型"""

    def test_model_creation(self):
        """测试模型创建"""
        result = SmartDecomposeResult(
            task_title="Task",
            task_notes="Notes",
            suggested_priority="hard",
            checklist=[
                ChecklistSuggestion(text="Step 1", priority="easy"),
            ]
        )

        assert result.task_title == "Task"
        assert result.task_notes == "Notes"
        assert result.suggested_priority == "hard"
        assert len(result.checklist) == 1

    def test_model_defaults(self):
        """测试模型默认值"""
        result = SmartDecomposeResult(task_title="Task")

        assert result.task_notes is None
        assert result.suggested_priority == "easy"
        assert result.checklist == []

    def test_checklist_suggestion_defaults(self):
        """测试子任务建议默认值"""
        item = ChecklistSuggestion(text="Step")

        assert item.text == "Step"
        assert item.priority == "medium"
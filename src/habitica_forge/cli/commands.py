"""任务操作命令模块"""

import asyncio
from datetime import datetime
from typing import List, Optional

import typer

from habitica_forge.clients.habitica import HabiticaClient
from habitica_forge.core.cache import get_cache_manager
from habitica_forge.models import ChecklistItem, TaskData
from habitica_forge.utils.logger import (
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
)

# 创建命令子应用
task_app = typer.Typer(name="task", help="任务管理命令")


@task_app.callback(invoke_without_command=True)
def task_callback(ctx: typer.Context):
    """任务管理命令"""
    pass


def _run_async(coro):
    """运行异步协程"""
    return asyncio.get_event_loop().run_until_complete(coro)


def _get_tag_map(client: HabiticaClient) -> dict:
    """获取标签 ID 到名称的映射"""
    tags = _run_async(client.get_tags())
    return {tag.id: tag.name for tag in tags}


def _invalidate_cache():
    """清除缓存"""
    cache_manager = get_cache_manager()
    cache_manager.invalidate_all()


def _resolve_task_id(task_id_or_index: str) -> str:
    """
    解析任务 ID（支持编号或完整 ID）

    Args:
        task_id_or_index: 任务编号（如 "1"）或完整/部分 UUID

    Returns:
        完整的 UUID 字符串

    Raises:
        ValueError: 如果编号不存在或无效
    """
    # 如果看起来像 UUID（包含字母和数字的组合，长度较长），直接返回
    if len(task_id_or_index) > 8:
        return task_id_or_index

    # 尝试作为编号查找
    cache_manager = get_cache_manager()
    uuid = cache_manager.index.get_uuid(task_id_or_index)

    if uuid:
        return uuid

    # 如果找不到编号映射，可能是用户直接输入的部分 UUID
    # 返回原值，让 API 尝试处理
    return task_id_or_index


# ============================================
# forge list 命令
# ============================================


@task_app.command("list")
def list_tasks(
    task_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="任务类型: todos, dailys, habits, rewards"
    ),
    all_tasks: bool = typer.Option(False, "--all", "-a", help="显示所有任务包括已完成"),
):
    """
    显示任务列表

    示例:
        forge list              # 显示所有待办任务
        forge list -t todos     # 只显示 Todo
        forge list -t habits    # 只显示习惯
        forge list -t dailys    # 只显示每日任务
        forge list --all        # 显示所有任务包括已完成
    """
    from habitica_forge.cli.viewer import (
        render_daily_list,
        render_habit_list,
        render_task_list,
    )

    async def _list():
        async with HabiticaClient() as client:
            # 获取任务
            tasks = await client.get_tasks()

            # 获取标签映射
            tag_map = _get_tag_map(client)

            # 过滤任务类型
            if task_type:
                type_map = {
                    "todos": "todo",
                    "dailys": "daily",
                    "habits": "habit",
                    "rewards": "reward",
                }
                filter_type = type_map.get(task_type, task_type)
                tasks = [t for t in tasks if t.type == filter_type]

            # 按类型分组渲染
            if task_type == "habits":
                render_habit_list(tasks, tag_map)
            elif task_type == "dailys":
                render_daily_list(tasks, tag_map)
            else:
                # 默认显示 todos
                todos = [t for t in tasks if t.type == "todo"]
                render_task_list(todos, tag_map, title="待办任务", show_completed=all_tasks)

    try:
        _run_async(_list())
    except Exception as e:
        print_error(f"获取任务失败: {e}")
        raise typer.Exit(1)


# ============================================
# forge show 命令
# ============================================


@task_app.command("show")
def show_task(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
):
    """
    显示任务详情

    示例:
        forge show 1          # 通过编号查看
        forge show abc12345   # 通过部分 ID 查看
    """
    from habitica_forge.cli.viewer import render_task_detail

    # 解析任务 ID
    resolved_id = _resolve_task_id(task_id)

    async def _show():
        async with HabiticaClient() as client:
            task = await client.get_task(resolved_id)
            tag_map = _get_tag_map(client)
            render_task_detail(task, tag_map)

    try:
        _run_async(_show())
    except Exception as e:
        print_error(f"获取任务详情失败: {e}")
        raise typer.Exit(1)


# ============================================
# forge add 命令
# ============================================


@task_app.command("add")
def add_task(
    text: str = typer.Argument(..., help="任务内容"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="任务备注"),
    priority: str = typer.Option(
        "easy", "--priority", "-p", help="难度: trivial, easy, medium, hard"
    ),
    due: Optional[str] = typer.Option(None, "--due", "-d", help="截止日期 (YYYY-MM-DD)"),
    tags: Optional[str] = typer.Option(None, "--tags", "-t", help="标签，逗号分隔"),
):
    """
    添加新任务

    示例:
        forge add "完成项目报告"
        forge add "写代码" -n "重要项目" -p hard
        forge add "读书" -d 2024-12-31 -t "学习,重要"
    """
    # 解析优先级
    priority_map = {
        "trivial": 0.1,
        "easy": 1.0,
        "medium": 1.5,
        "hard": 2.0,
    }
    priority_value = priority_map.get(priority.lower(), 1.0)

    # 解析日期
    due_date = None
    if due:
        try:
            due_date = datetime.strptime(due, "%Y-%m-%d")
        except ValueError:
            print_error(f"日期格式错误: {due}，应为 YYYY-MM-DD")
            raise typer.Exit(1)

    # 解析标签
    tag_names = []
    if tags:
        tag_names = [t.strip() for t in tags.split(",") if t.strip()]

    async def _add():
        async with HabiticaClient() as client:
            # 处理标签
            tag_ids = []
            if tag_names:
                for tag_name in tag_names:
                    tag = await client.get_or_create_tag(tag_name)
                    tag_ids.append(tag.id)

            # 创建任务
            task = TaskData(
                text=text,
                type="todo",
                notes=notes,
                priority=priority_value,
                date=due_date,
                tags=tag_ids,
            )

            created = await client.create_task(task)

            # 清除缓存
            _invalidate_cache()

            print_success(f"任务已创建: {created.id[:8]}")
            console.print(f"  [label]内容:[/] {created.text}")
            if created.notes:
                console.print(f"  [label]备注:[/] {created.notes}")

    try:
        _run_async(_add())
    except Exception as e:
        print_error(f"创建任务失败: {e}")
        raise typer.Exit(1)


# ============================================
# forge done 命令
# ============================================


@task_app.command("done")
def complete_task(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
):
    """
    完成任务

    示例:
        forge done 1          # 通过编号完成
        forge done abc12345   # 通过部分 ID 完成
    """
    # 解析任务 ID
    resolved_id = _resolve_task_id(task_id)

    async def _done():
        async with HabiticaClient() as client:
            # 先获取任务信息
            try:
                task = await client.get_task(resolved_id)
            except Exception:
                task = None

            # 完成任务
            await client.complete_task(resolved_id)

            # 清除缓存
            _invalidate_cache()

            task_text = task.text if task else task_id
            print_success(f"任务已完成: {task_text}")

    try:
        _run_async(_done())
    except Exception as e:
        print_error(f"完成任务失败: {e}")
        raise typer.Exit(1)


# ============================================
# forge undone 命令
# ============================================


@task_app.command("undone")
def undone_task(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
):
    """
    取消完成任务（将任务标记为未完成）

    示例:
        forge undone 1          # 通过编号取消
        forge undone abc12345   # 通过部分 ID 取消
    """
    # 解析任务 ID
    resolved_id = _resolve_task_id(task_id)

    async def _undone():
        async with HabiticaClient() as client:
            # 更新任务状态
            await client.update_task(resolved_id, completed=False)

            # 清除缓存
            _invalidate_cache()

            print_success(f"任务已标记为未完成")

    try:
        _run_async(_undone())
    except Exception as e:
        print_error(f"操作失败: {e}")
        raise typer.Exit(1)


# ============================================
# forge update 命令
# ============================================


@task_app.command("update")
def update_task(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
    text: Optional[str] = typer.Option(None, "--text", "-t", help="更新任务内容"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="更新备注"),
    priority: Optional[str] = typer.Option(
        None, "--priority", "-p", help="更新难度: trivial, easy, medium, hard"
    ),
):
    """
    更新任务

    示例:
        forge update 1 -t "新任务内容"
        forge update 1 -n "新备注" -p hard
        forge update abc12345 -t "新任务内容"
    """
    # 解析任务 ID
    resolved_id = _resolve_task_id(task_id)

    # 构建更新数据
    updates = {}
    if text:
        updates["text"] = text
    if notes:
        updates["notes"] = notes
    if priority:
        priority_map = {
            "trivial": 0.1,
            "easy": 1.0,
            "medium": 1.5,
            "hard": 2.0,
        }
        updates["priority"] = priority_map.get(priority.lower(), 1.0)

    if not updates:
        print_warning("没有指定要更新的内容")
        return

    async def _update():
        async with HabiticaClient() as client:
            await client.update_task(resolved_id, **updates)

            # 清除缓存
            _invalidate_cache()

            print_success(f"任务已更新")

    try:
        _run_async(_update())
    except Exception as e:
        print_error(f"更新任务失败: {e}")
        raise typer.Exit(1)


# ============================================
# forge delete 命令
# ============================================


@task_app.command("delete")
def delete_task(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
    force: bool = typer.Option(False, "--force", "-f", help="强制删除，不询问确认"),
):
    """
    删除任务

    示例:
        forge delete 1
        forge delete 1 -f
        forge delete abc12345
    """
    # 解析任务 ID
    resolved_id = _resolve_task_id(task_id)

    if not force:
        confirm = typer.confirm(f"确定要删除任务 {task_id} 吗?")
        if not confirm:
            print_info("已取消")
            return

    async def _delete():
        async with HabiticaClient() as client:
            await client.delete_task(resolved_id)

            # 清除缓存
            _invalidate_cache()

            print_success(f"任务已删除")

    try:
        _run_async(_delete())
    except Exception as e:
        print_error(f"删除任务失败: {e}")
        raise typer.Exit(1)


# ============================================
# 子任务命令组
# ============================================

sub_app = typer.Typer(name="sub", help="子任务 (Checklist) 操作")
task_app.add_typer(sub_app, name="sub")


@sub_app.command("add")
def add_subtask(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
    text: str = typer.Argument(..., help="子任务内容"),
):
    """
    添加子任务

    示例:
        forge sub add 1 "阅读文档"
        forge sub add abc12345 "阅读文档"
    """
    # 解析任务 ID
    resolved_id = _resolve_task_id(task_id)

    async def _add():
        async with HabiticaClient() as client:
            await client.add_checklist_item(resolved_id, text)

            # 清除缓存
            _invalidate_cache()

            print_success(f"子任务已添加: {text}")

    try:
        _run_async(_add())
    except Exception as e:
        print_error(f"添加子任务失败: {e}")
        raise typer.Exit(1)


@sub_app.command("done")
def complete_subtask(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
    item_id: str = typer.Argument(..., help="子任务编号或 ID"),
):
    """
    完成子任务

    示例:
        forge sub done 1 1
        forge sub done abc12345 xyz789
    """
    # 解析任务 ID
    resolved_task_id = _resolve_task_id(task_id)
    resolved_item_id = _resolve_task_id(item_id)

    async def _done():
        async with HabiticaClient() as client:
            await client.complete_checklist_item(resolved_task_id, resolved_item_id)

            # 清除缓存
            _invalidate_cache()

            print_success(f"子任务已完成")

    try:
        _run_async(_done())
    except Exception as e:
        print_error(f"完成子任务失败: {e}")
        raise typer.Exit(1)


@sub_app.command("undone")
def undone_subtask(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
    item_id: str = typer.Argument(..., help="子任务编号或 ID"),
):
    """
    取消完成子任务

    示例:
        forge sub undone 1 1
        forge sub undone abc12345 xyz789
    """
    # 解析任务 ID
    resolved_task_id = _resolve_task_id(task_id)
    resolved_item_id = _resolve_task_id(item_id)

    async def _undone():
        async with HabiticaClient() as client:
            await client.update_checklist_item(resolved_task_id, resolved_item_id, completed=False)

            # 清除缓存
            _invalidate_cache()

            print_success(f"子任务已取消完成")

    try:
        _run_async(_undone())
    except Exception as e:
        print_error(f"操作失败: {e}")
        raise typer.Exit(1)


@sub_app.command("delete")
def delete_subtask(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
    item_id: str = typer.Argument(..., help="子任务编号或 ID"),
):
    """
    删除子任务

    示例:
        forge sub delete 1 1
        forge sub delete abc12345 xyz789
    """
    # 解析任务 ID
    resolved_task_id = _resolve_task_id(task_id)
    resolved_item_id = _resolve_task_id(item_id)

    async def _delete():
        async with HabiticaClient() as client:
            await client.delete_checklist_item(resolved_task_id, resolved_item_id)

            # 清除缓存
            _invalidate_cache()

            print_success(f"子任务已删除")

    try:
        _run_async(_delete())
    except Exception as e:
        print_error(f"删除子任务失败: {e}")
        raise typer.Exit(1)
"""智能拆解命令模块"""

import asyncio
from typing import List, Optional

import typer

from habitica_forge.ai.llm_client import LLMClient, SmartDecomposeResult
from habitica_forge.cli.header import print_header
from habitica_forge.clients.habitica import HabiticaClient
from habitica_forge.core.bounty import trigger_bounty_drop
from habitica_forge.core.cache import get_cache_manager
from habitica_forge.core.config import get_settings
from habitica_forge.models import ChecklistItem, TaskData
from habitica_forge.utils.logger import (
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
)

# 创建智能命令子应用
smart_app = typer.Typer(name="smart", help="AI 智能拆解命令")


@smart_app.callback(invoke_without_command=True)
def smart_callback(ctx: typer.Context):
    """AI 智能拆解命令"""
    # 显示 Header（除了 help 命令）
    if ctx.invoked_subcommand != "help" and ctx.invoked_subcommand is not None:
        print_header()


# 优先级映射
PRIORITY_MAP = {
    "trivial": 0.1,
    "easy": 1.0,
    "medium": 1.5,
    "hard": 2.0,
}


def _resolve_task_id(task_id_or_index: str) -> str:
    """
    解析任务 ID（支持编号或完整 ID）

    Args:
        task_id_or_index: 任务编号（如 "1"）或完整/部分 UUID

    Returns:
        完整的 UUID 字符串
    """
    if len(task_id_or_index) > 8:
        return task_id_or_index

    cache_manager = get_cache_manager()
    uuid = cache_manager.index.get_uuid(task_id_or_index)

    if uuid:
        return uuid

    return task_id_or_index


async def _decompose_task(
    task_text: str,
    existing_checklist: Optional[List[str]] = None,
) -> SmartDecomposeResult:
    """
    调用 LLM 进行任务拆解

    Args:
        task_text: 任务内容
        existing_checklist: 现有的子任务列表

    Returns:
        拆解结果
    """
    current_settings = get_settings()
    async with LLMClient() as client:
        return await client.smart_decompose(
            task_text=task_text,
            style=current_settings.forge_style,
            existing_checklist=existing_checklist,
        )


async def _create_task_with_decomposition(
    client: HabiticaClient,
    result: SmartDecomposeResult,
) -> TaskData:
    """
    根据拆解结果创建任务

    Args:
        client: Habitica 客户端
        result: 拆解结果

    Returns:
        创建的任务
    """
    # 构建任务数据
    task = TaskData(
        text=result.task_title,
        type="todo",
        notes=result.task_notes,
        priority=PRIORITY_MAP.get(result.suggested_priority, 1.0),
        checklist=[
            ChecklistItem(text=item.text)
            for item in result.checklist
        ],
    )

    return await client.create_task(task)


async def _update_task_with_decomposition(
    client: HabiticaClient,
    task_id: str,
    result: SmartDecomposeResult,
    existing_task: TaskData,
) -> TaskData:
    """
    根据拆解结果更新任务

    Args:
        client: Habitica 客户端
        task_id: 任务 ID
        result: 拆解结果
        existing_task: 现有任务数据

    Returns:
        更新后的任务
    """
    # 构建更新数据
    updates = {}

    # 更新标题（如果改变）
    if result.task_title != existing_task.text:
        updates["text"] = result.task_title

    # 更新备注
    if result.task_notes:
        updates["notes"] = result.task_notes

    # 更新优先级
    new_priority = PRIORITY_MAP.get(result.suggested_priority, 1.0)
    if new_priority != existing_task.priority:
        updates["priority"] = new_priority

    # 更新 checklist
    if result.checklist:
        updates["checklist"] = [
            {"text": item.text, "completed": False}
            for item in result.checklist
        ]

    if updates:
        return await client.update_task(task_id, **updates)

    return existing_task


def _render_decompose_result(result: SmartDecomposeResult) -> None:
    """渲染拆解结果"""
    console.print()

    # 任务标题
    console.print(f"[title] {result.task_title}[/]")

    # 任务备注
    if result.task_notes:
        console.print(f"[dim]{result.task_notes}[/]")

    # 建议优先级
    priority_style = {
        "trivial": "dim",
        "easy": "green",
        "medium": "yellow",
        "hard": "red bold",
    }.get(result.suggested_priority, "white")
    console.print(f"[label]建议难度:[/] [{priority_style}]{result.suggested_priority}[/]")

    # 子任务列表
    if result.checklist:
        console.print(f"\n[label]拆解的子任务 ({len(result.checklist)}):[/]")
        for i, item in enumerate(result.checklist, 1):
            item_style = {
                "trivial": "dim",
                "easy": "green",
                "medium": "yellow",
                "hard": "red",
            }.get(item.priority, "white")
            console.print(
                f"  [yellow]{i}[/]. [dim][/][{item_style}]{item.text}[/]"
            )
    else:
        console.print("\n[dim]无需拆解为子任务[/]")

    console.print()


# ============================================
# forge smart-task 命令
# ============================================


@smart_app.command("task")
def smart_task(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
    keep_existing: bool = typer.Option(
        False, "--keep", "-k", help="保留现有子任务并在基础上优化"
    ),
):
    """
    智能拆解现有任务

    使用 AI 分析并拆解指定任务，生成可执行的子任务步骤。

    示例:
        forge smart task 1           # 拆解编号为 1 的任务
        forge smart task abc12345    # 拆解指定 ID 的任务
        forge smart task 1 --keep    # 保留现有子任务
    """
    # 解析任务 ID
    resolved_id = _resolve_task_id(task_id)

    async def _run():
        async with HabiticaClient() as habitica_client:
            # 获取现有任务
            with console.status("[bold cyan]正在获取任务信息...[/]"):
                existing_task = await habitica_client.get_task(resolved_id)

            if existing_task.completed:
                print_warning("任务已完成，无需拆解")
                return

            # 获取现有 checklist
            existing_checklist = None
            if keep_existing and existing_task.checklist:
                existing_checklist = [item.text for item in existing_task.checklist]

            # 调用 LLM 进行拆解
            with console.status("[bold yellow]正在锻造中...[/]"):
                result = await _decompose_task(
                    task_text=existing_task.text,
                    existing_checklist=existing_checklist,
                )

            # 更新任务
            updated_task = await _update_task_with_decomposition(
                habitica_client,
                resolved_id,
                result,
                existing_task,
            )

            # 清除缓存
            get_cache_manager().invalidate_all()

            # 显示结果
            print_success(f"任务已智能拆解: {updated_task.id[:8]}")
            _render_decompose_result(result)

    try:
        asyncio.run(_run())
    except Exception as e:
        print_error(f"智能拆解失败: {e}")
        raise typer.Exit(1)


# ============================================
# forge smart-add 命令
# ============================================


@smart_app.command("add")
def smart_add(
    text: str = typer.Argument(..., help="任务描述"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="任务备注"),
    no_decompose: bool = typer.Option(
        False, "--no-decompose", help="不拆解，只让 AI 优化标题"
    ),
):
    """
    智能添加任务（自动拆解）

    使用 AI 分析任务描述，优化标题并自动拆解为子任务。

    示例:
        forge smart add "完成项目报告"
        forge smart add "学习新技术" -n "重要技能"
        forge smart add "简单任务" --no-decompose
    """
    async def _run():
        async with HabiticaClient() as habitica_client:
            # 调用 LLM 进行拆解
            with console.status("[bold yellow]正在锻造中...[/]"):
                result = await _decompose_task(
                    task_text=text,
                    existing_checklist=None,
                )

            # 如果指定了备注，覆盖 AI 生成的备注
            if notes:
                result.task_notes = notes

            # 如果不需要拆解，清空 checklist
            if no_decompose:
                result.checklist = []

            # 创建任务
            created_task = await _create_task_with_decomposition(
                habitica_client,
                result,
            )

            # 清除缓存
            get_cache_manager().invalidate_all()

            # 检查悬赏掉落
            current_settings = get_settings()
            dropped = trigger_bounty_drop(
                task_id=created_task.id,
                task_text=created_task.text,
                priority=PRIORITY_MAP.get(result.suggested_priority, 1.0),
                task_type="todo",
                style=current_settings.forge_style,
            )

            # 显示结果
            print_success(f"任务已智能创建: {created_task.id[:8]}")
            _render_decompose_result(result)

            if dropped:
                print_info("🌟 悬赏触发！正在后台生成称号...")

    try:
        asyncio.run(_run())
    except Exception as e:
        print_error(f"智能创建失败: {e}")
        raise typer.Exit(1)


# ============================================
# forge smart-refine 命令（优化现有子任务）
# ============================================


@smart_app.command("refine")
def smart_refine(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
):
    """
    优化现有任务的子任务

    分析现有任务和子任务，进行优化和重组。

    示例:
        forge smart refine 1
        forge smart refine abc12345
    """
    # 解析任务 ID
    resolved_id = _resolve_task_id(task_id)

    async def _run():
        async with HabiticaClient() as habitica_client:
            # 获取现有任务
            with console.status("[bold cyan]正在获取任务信息...[/]"):
                existing_task = await habitica_client.get_task(resolved_id)

            if existing_task.completed:
                print_warning("任务已完成，无需优化")
                return

            # 获取现有 checklist
            existing_checklist = None
            if existing_task.checklist:
                existing_checklist = [item.text for item in existing_task.checklist]

            if not existing_checklist:
                print_info("任务没有子任务，将进行智能拆解")

            # 调用 LLM 进行优化
            with console.status("[bold yellow]正在锻造中...[/]"):
                result = await _decompose_task(
                    task_text=existing_task.text,
                    existing_checklist=existing_checklist,
                )

            # 更新任务
            updated_task = await _update_task_with_decomposition(
                habitica_client,
                resolved_id,
                result,
                existing_task,
            )

            # 清除缓存
            get_cache_manager().invalidate_all()

            # 显示结果
            print_success(f"任务子任务已优化: {updated_task.id[:8]}")
            _render_decompose_result(result)

    try:
        asyncio.run(_run())
    except Exception as e:
        print_error(f"优化失败: {e}")
        raise typer.Exit(1)
"""游戏化命令模块

提供统一的任务游戏化入口：
- forge gamify add <text>: 智能创建并游戏化任务
- forge gamify task <id>: 智能拆解并游戏化现有任务
- forge gamify refine <id>: 优化现有子任务
- forge gamify revert <id>: 还原游戏化
- forge gamify backlog: 批量游戏化
"""

import asyncio
from typing import Dict, List, Optional

import nest_asyncio
import typer
from rich.table import Table

# 允许嵌套事件循环，解决 questionary 与 asyncio.run() 冲突
nest_asyncio.apply()

from habitica_forge.ai.llm_client import LLMClient, SmartDecomposeResult
from habitica_forge.ai.session import DecomposeSession
from habitica_forge.cli.interactive import InteractiveDecomposeUI
from habitica_forge.clients.habitica import HabiticaClient
from habitica_forge.core.bounty import (
    trigger_bounty_drop,
    trigger_chain_completion_reward,
    calculate_chain_completion_bonus,
)
from habitica_forge.core.cache import get_cache_manager
from habitica_forge.core.config import get_settings
from habitica_forge.models import ChecklistItem, TaskData
from habitica_forge.quest.tags import (
    ForgeTagPrefix,
    ForgeTags,
    build_forge_tags_from_result,
    ensure_tags_exist,
    get_tag_ids_for_forge_tags,
    parse_forge_tags,
    LEGENDARY_TAG,
)
from habitica_forge.quest.legendary import LegendaryType
from habitica_forge.styles import get_style_config
from habitica_forge.styles.images import render_image_markdown, get_image_by_id
from habitica_forge.utils.logger import (
    console,
    print_error,
    print_info,
    print_success,
    print_warning,
)

# 创建游戏化命令子应用
gamify_app = typer.Typer(name="gamify", help="任务游戏化命令（统一入口）")

# 优先级映射
PRIORITY_MAP = {
    "trivial": 0.1,
    "easy": 1.0,
    "medium": 1.5,
    "hard": 2.0,
}


def _resolve_task_id(task_id_or_index: str) -> str:
    """解析任务 ID"""
    if len(task_id_or_index) > 8:
        return task_id_or_index

    cache_manager = get_cache_manager()
    uuid = cache_manager.index.get_uuid(task_id_or_index)

    if uuid:
        return uuid

    return task_id_or_index


def _render_quest_commission(
    result: SmartDecomposeResult,
    task_id: Optional[str] = None,
    is_new: bool = True,
) -> None:
    """渲染任务委托书（游戏化输出）

    V2 阶段四增强：
    - 支持传奇任务类型显示
    - 章节进度可视化
    - 任务链徽章

    V2 阶段五简化：
    - 移除双名结构和奖励感显示
    """
    console.print()

    # 委托书头部
    console.print("[bold cyan]═══════════════════════════════════════════[/]")
    console.print("[bold cyan]           ✦ 任务委托书 ✦              [/]")
    console.print("[bold cyan]═══════════════════════════════════════════[/]")

    # 任务链徽章（V2 阶段四）
    if result.chain_name:
        chain_idx = result.chain_index or 1
        if result.legendary_type == "chain":
            console.print(f"\n[bold magenta]【{result.chain_name}】系列任务 · 第 {chain_idx} 章[/]")

    # 任务类型标签（增强显示）
    if result.quest_type:
        # 优先使用 legendary_type
        display_type = result.legendary_type or result.quest_type
        type_labels = {
            "main": "[bold green]【主线任务】[/]",
            "side": "[bold blue]【支线任务】[/]",
            "legendary": "[bold magenta]【传奇任务】[/]",
            "expedition": "[bold cyan]【远征任务】[/]",
            "campaign": "[bold yellow]【战役任务】[/]",
            "escort": "[bold white]【护送任务】[/]",
            "saga": "[bold red]【史诗任务】[/]",
            "chain": "[bold purple]【任务链】[/]",
        }
        type_label = type_labels.get(display_type, "")
        if type_label:
            console.print(type_label)

    # 游戏名（主标题）
    console.print(f"\n[bold yellow]▶ {result.quest_title or result.task_title}[/]")

    # 任务属性行
    attrs = []
    if result.archetype:
        archetype_names = {
            "cleanup": "清理", "repair": "修复", "explore": "探索",
            "craft": "制作", "communicate": "沟通", "learn": "学习",
            "battle": "战斗", "supply": "补给",
        }
        attrs.append(f"类型: [cyan]{archetype_names.get(result.archetype, result.archetype)}[/]")
    if result.location:
        attrs.append(f"地点: [green]{result.location}[/]")

    if attrs:
        console.print(f"\n[dim]{' │ '.join(attrs)}[/]")

    # 任务备注
    if result.task_notes:
        console.print(f"\n[dim italic]{result.task_notes}[/]")

    # 建议优先级
    priority_style = {
        "trivial": "dim",
        "easy": "green",
        "medium": "yellow",
        "hard": "red bold",
    }.get(result.suggested_priority, "white")
    console.print(f"[bold]难度: [/][{priority_style}]{result.suggested_priority}[/]")

    # 已选择的图片
    if result.image_ids:
        console.print(f"\n[bold]选择图片 ({len(result.image_ids)}):[/]")
        for img_id in result.image_ids:
            img = get_image_by_id(img_id)
            if img:
                console.print(f"  🖼️ [cyan]{img.title}[/] [dim]({img_id})[/]")

    # 章节化子任务（V2 阶段四增强显示）
    if result.chapters:
        console.print(f"\n[bold]任务阶段 ({len(result.chapters)} 章):[/]")

        # 计算总进度
        total_items = sum(len(ch.items) for ch in result.chapters)
        console.print(f"[dim]共 {total_items} 个步骤[/]\n")

        for chapter in result.chapters:
            # 章节标题
            console.print(f"  [bold cyan]◆ 阶段 {chapter.chapter_number}: {chapter.chapter_title}[/]")

            for item in chapter.items:
                item_style = {
                    "trivial": "dim",
                    "easy": "green",
                    "medium": "yellow",
                    "hard": "red",
                }.get(item.priority, "white")
                console.print(f"    [dim]○[/] [{item_style}]{item.text}[/]")
            console.print()  # 章节间空行

    elif result.checklist:
        console.print(f"\n[bold]任务步骤 ({len(result.checklist)}):[/]")
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

    # 传奇任务提示（增强显示）
    if result.is_legendary:
        legendary_hints = {
            "main": "这是一个主线任务，关乎大局！",
            "expedition": "这是一次远征，准备好迎接挑战！",
            "campaign": "这是一场战役，需要分阶段攻克！",
            "escort": "这个任务需要持续关注！",
            "saga": "这是一个史诗级任务，将载入史册！",
            "chain": "这是系列任务的一部分！",
        }
        display_type = result.legendary_type or result.quest_type
        hint = legendary_hints.get(display_type, "这是一个传奇任务，建议分阶段完成！")
        console.print(f"\n[bold magenta]⚔ {hint}[/]")

    console.print("\n[bold cyan]═══════════════════════════════════════════[/]")
    console.print()


async def _gamify_and_decompose(
    task_text: str,
    style: str,
    existing_checklist: Optional[List[str]] = None,
    task_type: str = "todo",
) -> SmartDecomposeResult:
    """调用 LLM 进行游戏化和拆解"""
    async with LLMClient() as client:
        return await client.smart_decompose(
            task_text=task_text,
            style=style,
            existing_checklist=existing_checklist,
            task_type=task_type,
        )


async def _create_task_with_result(
    client: HabiticaClient,
    result: SmartDecomposeResult,
    task_type: str = "todo",
) -> TaskData:
    """根据游戏化结果创建任务

    V2 阶段五改进：
    - 使用 Tags 替代 notes 中的元数据存储
    - 支持指定任务类型
    - 支持图片注入到 notes

    Args:
        client: Habitica 客户端
        result: 游戏化结果
        task_type: 任务类型 (todo/daily/habit/reward)
    """
    # 构建 Forge 标签
    forge_tags = build_forge_tags_from_result(result)
    forge_tag_names = forge_tags.to_list()

    # 获取现有标签并确保需要的标签存在
    tags = await client.get_tags()
    tag_name_to_id = {tag.name: tag.id for tag in tags}

    if forge_tag_names:
        await ensure_tags_exist(client, forge_tag_names, tag_name_to_id)

    # 获取标签 ID
    tag_ids = get_tag_ids_for_forge_tags(forge_tag_names, tag_name_to_id)

    # 构建备注（包含用户备注和图片）
    notes_parts = []

    # 添加图片（在备注顶部）
    if result.image_ids:
        for img_id in result.image_ids:
            img_md = render_image_markdown(img_id)
            if img_md:
                notes_parts.append(img_md)

    # 添加用户备注
    if result.task_notes:
        notes_parts.append(result.task_notes)

    notes = "\n\n".join(notes_parts) if notes_parts else ""

    # 构建任务数据（使用指定的任务类型和标签）
    task = TaskData(
        text=result.quest_title or result.task_title,
        type=task_type,
        tags=tag_ids,
        notes=notes,
        priority=PRIORITY_MAP.get(result.suggested_priority, 1.0),
        checklist=[
            ChecklistItem(text=item.text)
            for item in result.checklist
        ],
    )

    return await client.create_task(task)


async def _update_task_with_result(
    client: HabiticaClient,
    task_id: str,
    result: SmartDecomposeResult,
    existing_task: TaskData,
) -> TaskData:
    """根据游戏化结果更新任务

    V2 阶段五改进：
    - 使用 Tags 替代 notes 中的元数据存储
    - 支持图片注入到 notes
    """
    # 构建 Forge 标签
    forge_tags = build_forge_tags_from_result(result)
    forge_tag_names = forge_tags.to_list()

    # 获取现有标签并确保需要的标签存在
    tags = await client.get_tags()
    tag_name_to_id = {tag.name: tag.id for tag in tags}

    if forge_tag_names:
        await ensure_tags_exist(client, forge_tag_names, tag_name_to_id)

    # 获取新标签 ID
    new_tag_ids = get_tag_ids_for_forge_tags(forge_tag_names, tag_name_to_id)

    # 保留用户原有的非 Forge 标签
    id_to_name = {tag.id: tag.name for tag in tags}
    existing_non_forge_ids = []
    for tag_id in existing_task.tags:
        tag_name = id_to_name.get(tag_id, "")
        # 排除 Forge 相关标签（以 forge:, chain:, archetype:, location: 开头）
        if not any(tag_name.startswith(prefix.value) for prefix in ForgeTagPrefix):
            existing_non_forge_ids.append(tag_id)

    # 合并标签
    all_tag_ids = list(set(existing_non_forge_ids + new_tag_ids))

    # 构建更新数据
    updates = {}

    # 更新标题
    if result.quest_title:
        updates["text"] = result.quest_title

    # 构建备注（包含图片和用户备注）
    notes_parts = []

    # 添加图片（在备注顶部）
    if result.image_ids:
        for img_id in result.image_ids:
            img_md = render_image_markdown(img_id)
            if img_md:
                notes_parts.append(img_md)

    # 添加用户备注
    if result.task_notes:
        notes_parts.append(result.task_notes)
    elif existing_task.notes:
        notes_parts.append(existing_task.notes)

    notes = "\n\n".join(notes_parts) if notes_parts else ""
    updates["notes"] = notes

    # 更新标签
    if all_tag_ids != existing_task.tags:
        updates["tags"] = all_tag_ids

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


async def _interactive_refine_loop(
    session: DecomposeSession,
    llm_client: LLMClient,
) -> bool:
    """交互式调整循环"""
    current_settings = get_settings()
    ui = InteractiveDecomposeUI(session, style=current_settings.forge_style)

    while True:
        # 显示预览
        ui.render_preview()

        # 显示主菜单
        action = ui.main_menu()

        if action == "confirm":
            return True

        elif action == "quit":
            if ui.confirm_quit():
                return False

        elif action == "edit_checklist":
            index = ui.select_checklist_item()
            if index is not None:
                ui.edit_checklist_item(index)

        elif action == "add_checklist":
            ui.add_checklist_item()

        elif action == "delete_checklist":
            ui.delete_checklist_item()

        elif action == "edit_title":
            ui.edit_title()

        elif action == "edit_notes":
            ui.edit_notes()

        elif action == "edit_priority":
            ui.edit_priority()

        elif action == "add_image":
            ui.add_image()

        elif action == "remove_image":
            ui.remove_image()

        elif action == "ai_refine":
            # REPL 风格的多轮对话
            console.print("\n[bold cyan]═══════════════════════════════════════[/]")
            console.print("[bold cyan]     AI 对话模式 (输入 'menu' 返回菜单)     [/]")
            console.print("[bold cyan]═══════════════════════════════════════[/]\n")

            while True:
                feedback = ui.get_natural_feedback()

                if feedback is None:
                    break

                if feedback == "CONFIRM":
                    return True

                if feedback.lower() == "menu":
                    break

                # AI 根据用户反馈调整
                with console.status("[bold yellow]AI 正在思考并调整...[/]"):
                    new_result = await llm_client.refine_decompose_with_context(
                        session=session,
                        user_context=feedback,
                        style=current_settings.forge_style,
                    )
                session.current_result = new_result
                ui._modified = True

                # 重新显示预览
                ui.render_preview()

        elif action == "show_history":
            ui.show_conversation_history()
            input("\n按回车键继续...")


# ============================================
# forge gamify add 命令
# ============================================


@gamify_app.command("add")
def gamify_add(
    text: str = typer.Argument(..., help="任务描述"),
    task_type: str = typer.Option(
        ..., "--type", "-t",
        help="任务类型: todo, daily, habit, reward（必填）"
    ),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="任务备注"),
    no_decompose: bool = typer.Option(
        False, "--no-decompose", help="不拆解，只进行游戏化"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="跳过预览，直接创建"
    ),
    interactive: bool = typer.Option(
        True, "--interactive/-i", "--no-interactive", help="交互式调整模式"
    ),
):
    """
    智能创建并游戏化任务

    使用 AI 分析任务描述，生成游戏化标题、任务原型、地点、奖励感，
    并自动拆解为阶段化的子任务。

    必须指定任务类型: todo, daily, habit, reward

    示例:
        forge gamify add "完成项目报告" -t todo
        forge gamify add "每天跑步" -t daily
        forge gamify add "学习新技术" -t habit -n "重要技能"
        forge gamify add "简单任务" -t todo --no-decompose
        forge gamify add "任务" -t todo -f  # 跳过预览直接创建
    """
    # 验证任务类型
    valid_types = ["todo", "daily", "habit", "reward"]
    task_type_lower = task_type.lower()
    if task_type_lower not in valid_types:
        print_error(f"无效的任务类型: {task_type}")
        print_info(f"有效类型: {', '.join(valid_types)}")
        raise typer.Exit(1)

    async def _run():
        async with HabiticaClient() as habitica_client:
            async with LLMClient() as llm_client:
                # 调用 LLM 进行游戏化和拆解
                with console.status("[bold yellow]正在锻造任务委托书...[/]"):
                    current_settings = get_settings()
                    result = await _gamify_and_decompose(
                        task_text=text,
                        style=current_settings.forge_style,
                        existing_checklist=None,
                        task_type=task_type_lower,
                    )

                # 如果指定了备注，覆盖 AI 生成的备注
                if notes:
                    result.task_notes = notes

                # 如果不需要拆解，清空 checklist
                if no_decompose:
                    result.checklist = []

                # 创建会话
                session = DecomposeSession(
                    original_input=text,
                    current_result=result,
                    is_new_task=True,
                )

                if not force:
                    if interactive:
                        # 交互式调整模式
                        confirmed = await _interactive_refine_loop(session, llm_client)
                        if not confirmed:
                            print_info("已取消创建任务")
                            return
                        result = session.current_result
                    else:
                        # 非交互式模式，显示预览并确认
                        _render_quest_commission(result, is_new=True)
                        try:
                            confirm_input = input("确认创建? [y/N]: ").strip().lower()
                            if confirm_input not in ("y", "yes", "是"):
                                print_info("已取消创建任务")
                                return
                        except (EOFError, KeyboardInterrupt):
                            print_info("已取消创建任务")
                            return

                # 创建任务（使用指定的类型）
                created_task = await _create_task_with_result(
                    habitica_client,
                    result,
                    task_type=task_type_lower,
                )

                # 清除缓存
                get_cache_manager().invalidate_all()

                # 检查悬赏掉落
                current_settings = get_settings()
                dropped = trigger_bounty_drop(
                    task_id=created_task.id,
                    task_text=created_task.text,
                    priority=PRIORITY_MAP.get(result.suggested_priority, 1.0),
                    task_type=task_type_lower,
                    style=current_settings.forge_style,
                )

                # 显示结果
                print_success(f"任务已创建: {created_task.id[:8]}")

                if dropped:
                    print_info("🌟 悬赏触发！正在后台生成称号...")

    try:
        asyncio.run(_run())
    except Exception as e:
        print_error(f"创建失败: {e}")
        raise typer.Exit(1)


# ============================================
# forge gamify task 命令
# ============================================


@gamify_app.command("task")
def gamify_task(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
    keep_existing: bool = typer.Option(
        False, "--keep", "-k", help="保留现有子任务并在基础上优化"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="跳过预览，直接更新"
    ),
    interactive: bool = typer.Option(
        True, "--interactive/-i", "--no-interactive", help="交互式调整模式"
    ),
):
    """
    智能拆解并游戏化现有任务

    使用 AI 分析指定任务，进行游戏化包装并拆解为阶段化的子任务。

    示例:
        forge gamify task 1           # 拆解编号为 1 的任务
        forge gamify task abc12345    # 拆解指定 ID 的任务
        forge gamify task 1 --keep    # 保留现有子任务
        forge gamify task 1 -f        # 跳过预览直接更新
    """
    resolved_id = _resolve_task_id(task_id)

    async def _run():
        async with HabiticaClient() as habitica_client:
            # 获取现有任务
            with console.status("[bold cyan]正在获取任务信息...[/]"):
                existing_task = await habitica_client.get_task(resolved_id)

            if existing_task.completed:
                print_warning("任务已完成，无需处理")
                return

            # 获取现有 checklist
            existing_checklist = None
            if keep_existing and existing_task.checklist:
                existing_checklist = [item.text for item in existing_task.checklist]

            # 调用 LLM 进行游戏化和拆解
            with console.status("[bold yellow]正在锻造任务委托书...[/]"):
                current_settings = get_settings()
                result = await _gamify_and_decompose(
                    task_text=existing_task.text,
                    style=current_settings.forge_style,
                    existing_checklist=existing_checklist,
                    task_type=existing_task.type,
                )

            # 创建会话
            session = DecomposeSession(
                original_input=existing_task.text,
                current_result=result,
                is_new_task=False,
                existing_task_id=resolved_id,
            )

            if not force:
                async with LLMClient() as llm_client:
                    if interactive:
                        # 交互式调整模式
                        confirmed = await _interactive_refine_loop(session, llm_client)
                        if not confirmed:
                            print_info("已取消操作")
                            return
                        result = session.current_result
                    else:
                        # 非交互式模式，显示预览并确认
                        _render_quest_commission(result, task_id=resolved_id, is_new=False)
                        try:
                            confirm_input = input("确认更新任务? [y/N]: ").strip().lower()
                            if confirm_input not in ("y", "yes", "是"):
                                print_info("已取消操作")
                                return
                        except (EOFError, KeyboardInterrupt):
                            print_info("已取消操作")
                            return

            # 更新任务
            updated_task = await _update_task_with_result(
                habitica_client,
                resolved_id,
                result,
                existing_task,
            )

            # 清除缓存
            get_cache_manager().invalidate_all()

            # 显示结果
            print_success(f"任务已游戏化: {updated_task.id[:8]}")

    try:
        asyncio.run(_run())
    except Exception as e:
        print_error(f"操作失败: {e}")
        raise typer.Exit(1)


# ============================================
# forge gamify refine 命令
# ============================================


@gamify_app.command("refine")
def gamify_refine(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
    force: bool = typer.Option(
        False, "--force", "-f", help="跳过预览，直接更新"
    ),
    interactive: bool = typer.Option(
        True, "--interactive/-i", "--no-interactive", help="交互式调整模式"
    ),
):
    """
    优化现有任务的子任务

    分析现有任务和子任务，进行游戏化重组和优化。

    示例:
        forge gamify refine 1
        forge gamify refine abc12345
        forge gamify refine 1 -f  # 跳过预览直接更新
    """
    resolved_id = _resolve_task_id(task_id)

    async def _run():
        async with HabiticaClient() as habitica_client:
            # 获取现有任务
            with console.status("[bold cyan]正在获取任务信息...[/]"):
                existing_task = await habitica_client.get_task(resolved_id)

            if existing_task.completed:
                print_warning("任务已完成，无需处理")
                return

            # 获取现有 checklist
            existing_checklist = None
            if existing_task.checklist:
                existing_checklist = [item.text for item in existing_task.checklist]

            if not existing_checklist:
                print_info("任务没有子任务，将进行智能拆解")

            # 调用 LLM 进行优化
            with console.status("[bold yellow]正在优化子任务...[/]"):
                current_settings = get_settings()
                result = await _gamify_and_decompose(
                    task_text=existing_task.text,
                    style=current_settings.forge_style,
                    existing_checklist=existing_checklist,
                    task_type=existing_task.type,
                )

            # 创建会话
            session = DecomposeSession(
                original_input=existing_task.text,
                current_result=result,
                is_new_task=False,
                existing_task_id=resolved_id,
            )

            if not force:
                async with LLMClient() as llm_client:
                    if interactive:
                        confirmed = await _interactive_refine_loop(session, llm_client)
                        if not confirmed:
                            print_info("已取消操作")
                            return
                        result = session.current_result
                    else:
                        _render_quest_commission(result, task_id=resolved_id, is_new=False)
                        try:
                            confirm_input = input("确认更新任务? [y/N]: ").strip().lower()
                            if confirm_input not in ("y", "yes", "是"):
                                print_info("已取消操作")
                                return
                        except (EOFError, KeyboardInterrupt):
                            print_info("已取消操作")
                            return

            # 更新任务
            updated_task = await _update_task_with_result(
                habitica_client,
                resolved_id,
                result,
                existing_task,
            )

            # 清除缓存
            get_cache_manager().invalidate_all()

            print_success(f"任务子任务已优化: {updated_task.id[:8]}")

    try:
        asyncio.run(_run())
    except Exception as e:
        print_error(f"优化失败: {e}")
        raise typer.Exit(1)


# ============================================
# forge gamify revert 命令
# ============================================


@gamify_app.command("revert")
def gamify_revert(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
):
    """
    还原任务的游戏化标签

    移除任务的 Forge 相关标签（传奇、原型、地点、任务链等）。

    示例:
        forge gamify revert 1
        forge gamify revert abc12345
    """
    resolved_id = _resolve_task_id(task_id)

    async def _run():
        async with HabiticaClient() as habitica_client:
            # 获取任务
            with console.status("[bold cyan]正在获取任务信息...[/]"):
                task = await habitica_client.get_task(resolved_id)

            # 获取标签映射
            tags = await habitica_client.get_tags()
            id_to_name = {tag.id: tag.name for tag in tags}

            # 检查是否有 Forge 标签
            forge_tag_ids = []
            forge_tag_names = []
            for tag_id in task.tags:
                tag_name = id_to_name.get(tag_id, "")
                if any(tag_name.startswith(prefix.value) for prefix in ForgeTagPrefix):
                    forge_tag_ids.append(tag_id)
                    forge_tag_names.append(tag_name)

            if not forge_tag_names:
                print_info("此任务没有游戏化标签")
                return

            # 显示当前状态
            console.print("\n[bold cyan]═══════════════════════════════════════════[/]")
            console.print("[bold cyan]           还原游戏化                     [/]")
            console.print("[bold cyan]═══════════════════════════════════════════[/]")

            console.print(f"\n[bold]当前标题:[/] {task.text}")
            console.print(f"[bold]游戏化标签:[/] {', '.join(forge_tag_names)}")

            # 准备更新：移除 Forge 标签
            new_tag_ids = [tid for tid in task.tags if tid not in forge_tag_ids]

            # 确认
            console.print()
            console.print("[dim]将移除以上游戏化标签[/]")

            try:
                confirm = input("\n确认还原? [y/N]: ").strip().lower()
                if confirm not in ("y", "yes", "是"):
                    print_info("已取消")
                    return
            except (EOFError, KeyboardInterrupt):
                print_info("已取消")
                return

            # 应用更新
            await habitica_client.update_task(resolved_id, tags=new_tag_ids)

            # 清除缓存
            get_cache_manager().invalidate_all()

            print_success(f"任务已还原: {resolved_id[:8]}")
            console.print(f"[dim]已移除 {len(forge_tag_names)} 个游戏化标签[/]")

    try:
        asyncio.run(_run())
    except Exception as e:
        print_error(f"还原失败: {e}")
        raise typer.Exit(1)


# ============================================
# forge gamify backlog 命令
# ============================================


@gamify_app.command("backlog")
def gamify_backlog(
    limit: int = typer.Option(
        10, "--limit", "-l", help="最大处理任务数"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="仅预览，不实际修改"
    ),
    skip_gamified: bool = typer.Option(
        True, "--skip-gamified/--include-gamified", help="跳过已游戏化的任务"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="跳过确认，直接处理"
    ),
):
    """
    批量游戏化待办任务

    对多个未完成的 Todo 任务进行批量游戏化处理。

    示例:
        forge gamify backlog            # 游戏化最多 10 个任务
        forge gamify backlog -l 20      # 游戏化最多 20 个任务
        forge gamify backlog --dry-run  # 仅预览
        forge gamify backlog -f         # 跳过确认
    """
    async def _run():
        async with HabiticaClient() as habitica_client:
            # 获取标签映射
            tags = await habitica_client.get_tags()
            tag_name_to_id = {tag.name: tag.id for tag in tags}
            id_to_name = {tag.id: tag.name for tag in tags}

            # 获取未完成的 Todo
            with console.status("[bold cyan]正在获取任务列表...[/]"):
                tasks = await habitica_client.get_tasks("todos")

            # 过滤
            uncompleted = [t for t in tasks if not t.completed]
            if skip_gamified:
                uncompleted = [t for t in uncompleted if not _has_forge_tags(t, id_to_name)]

            uncompleted = uncompleted[:limit]

            if not uncompleted:
                print_info("没有需要游戏化的任务")
                return

            console.print(f"\n[bold]找到 {len(uncompleted)} 个待游戏化任务:[/]\n")

            # 显示任务列表
            table = Table(show_header=True, header_style="bold cyan")
            table.add_column("#", style="dim", width=4)
            table.add_column("当前标题")
            table.add_column("状态", width=10)

            for i, task in enumerate(uncompleted, 1):
                status = "[green]已游戏化[/]" if _has_forge_tags(task, id_to_name) else "[dim]待处理[/]"
                table.add_row(str(i), task.text[:50], status)

            console.print(table)

            if dry_run:
                console.print("\n[dim]--dry-run 模式，不实际修改任务[/]")
                return

            # 确认
            if not force:
                console.print()
                try:
                    confirm = input(f"确认游戏化以上 {len(uncompleted)} 个任务? [y/N]: ").strip().lower()
                    if confirm not in ("y", "yes", "是"):
                        print_info("已取消")
                        return
                except (EOFError, KeyboardInterrupt):
                    print_info("已取消")
                    return

            # 批量游戏化
            current_settings = get_settings()
            success_count = 0

            for i, task in enumerate(uncompleted, 1):
                console.print(f"\n[dim][{i}/{len(uncompleted)}][/] 正在处理: {task.text[:30]}...")

                try:
                    result = await _gamify_and_decompose(
                        task_text=task.text,
                        style=current_settings.forge_style,
                        existing_checklist=[item.text for item in task.checklist] if task.checklist else None,
                        task_type=task.type,
                    )

                    # 确保 Forge 标签存在
                    forge_tags = build_forge_tags_from_result(result)
                    if forge_tags.to_list():
                        await ensure_tags_exist(habitica_client, forge_tags.to_list(), tag_name_to_id)
                        # 更新映射
                        tag_name_to_id = {tag.name: tag.id for tag in await habitica_client.get_tags()}

                    updates = _apply_gamification_updates(task, result, tag_name_to_id, id_to_name)
                    await habitica_client.update_task(task.id, **updates)
                    success_count += 1
                    console.print(f"  [green]✓ 已游戏化: {result.quest_title or task.text[:30]}[/]")
                except Exception as e:
                    console.print(f"  [red]✗ 失败: {e}[/]")

            # 清除缓存
            get_cache_manager().invalidate_all()

            console.print()
            print_success(f"批量游戏化完成: {success_count}/{len(uncompleted)} 成功")

    try:
        asyncio.run(_run())
    except Exception as e:
        print_error(f"批量游戏化失败: {e}")
        raise typer.Exit(1)


def _has_forge_tags(task: TaskData, id_to_name: Dict[str, str]) -> bool:
    """检查任务是否有 Forge 标签"""
    for tag_id in task.tags:
        tag_name = id_to_name.get(tag_id, "")
        if any(tag_name.startswith(prefix.value) for prefix in ForgeTagPrefix):
            return True
    return False


def _apply_gamification_updates(
    task: TaskData,
    result: SmartDecomposeResult,
    tag_name_to_id: Dict[str, str],
    id_to_name: Dict[str, str],
) -> dict:
    """应用游戏化结果到任务（用于批量处理）

    V2 阶段五：使用 Tags 替代元数据，支持图片
    """
    updates = {}

    # 更新标题
    if result.quest_title:
        updates["text"] = result.quest_title

    # 构建 Forge 标签
    forge_tags = build_forge_tags_from_result(result)
    forge_tag_names = forge_tags.to_list()

    # 获取新标签 ID
    new_tag_ids = get_tag_ids_for_forge_tags(forge_tag_names, tag_name_to_id)

    # 保留用户原有的非 Forge 标签
    existing_non_forge_ids = []
    for tag_id in task.tags:
        tag_name = id_to_name.get(tag_id, "")
        if not any(tag_name.startswith(prefix.value) for prefix in ForgeTagPrefix):
            existing_non_forge_ids.append(tag_id)

    # 合并标签
    all_tag_ids = list(set(existing_non_forge_ids + new_tag_ids))
    if all_tag_ids != task.tags:
        updates["tags"] = all_tag_ids

    # 构建备注（包含图片和用户备注）
    notes_parts = []

    # 添加图片
    if result.image_ids:
        for img_id in result.image_ids:
            img_md = render_image_markdown(img_id)
            if img_md:
                notes_parts.append(img_md)

    # 添加用户备注
    if result.task_notes:
        notes_parts.append(result.task_notes)
    elif task.notes:
        notes_parts.append(task.notes)

    notes = "\n\n".join(notes_parts) if notes_parts else ""
    updates["notes"] = notes

    return updates


# ============================================
# forge gamify chain 命令 (V2 阶段四)
# ============================================

# 创建任务链子应用
chain_app = typer.Typer(name="chain", help="任务链管理")
gamify_app.add_typer(chain_app, name="chain")


@chain_app.command("create")
def chain_create(
    name: str = typer.Argument(..., help="任务链名称"),
    description: Optional[str] = typer.Option(
        None, "--desc", "-d", help="任务链描述"
    ),
):
    """
    创建新的任务链

    示例:
        forge gamify chain create "北境迁移计划"
        forge gamify chain create "项目重构" -d "三阶段重构计划"
    """
    from habitica_forge.quest import get_chain_manager

    manager = get_chain_manager()
    current_settings = get_settings()

    # 检查是否已存在
    if manager.get_chain(name):
        print_warning(f"任务链 '{name}' 已存在")
        return

    # 创建任务链
    chain = manager.create_chain(
        name=name,
        description=description,
        style=current_settings.forge_style,
    )

    print_success(f"任务链已创建: {name}")
    console.print(f"[dim]使用 'forge gamify chain add {name} <任务编号>' 添加任务[/]")


@chain_app.command("add")
def chain_add(
    name: str = typer.Argument(..., help="任务链名称"),
    task_ids: List[str] = typer.Argument(..., help="任务编号或 ID（可多个）"),
):
    """
    将任务添加到任务链

    示例:
        forge gamify chain add "北境迁移计划" 1 2 3
        forge gamify chain add "项目重构" abc12345
    """
    from habitica_forge.quest import get_chain_manager

    manager = get_chain_manager()
    chain = manager.get_chain(name)

    if not chain:
        print_error(f"任务链 '{name}' 不存在")
        print_info(f"使用 'forge gamify chain create {name}' 创建")
        raise typer.Exit(1)

    added_count = 0
    for task_id in task_ids:
        resolved_id = _resolve_task_id(task_id)
        chain.add_task(resolved_id)
        added_count += 1

    # 保存任务链状态
    manager.update_chain(chain)

    print_success(f"已添加 {added_count} 个任务到任务链 '{name}'")


@chain_app.command("list")
def chain_list():
    """
    列出所有任务链

    示例:
        forge gamify chain list
    """
    from habitica_forge.quest import get_chain_manager

    manager = get_chain_manager()
    chains = manager.get_all_chains()

    if not chains:
        print_info("暂无任务链")
        print_info("使用 'forge gamify chain create <名称>' 创建")
        return

    console.print("\n[bold]任务链列表:[/]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("名称", width=20)
    table.add_column("描述", width=30)
    table.add_column("任务数", width=8)
    table.add_column("进度", width=15)

    for chain in chains:
        completed, total = chain.get_progress()
        progress = f"{completed}/{total}" if total > 0 else "-"
        desc = chain.description[:28] + "..." if chain.description and len(chain.description) > 30 else (chain.description or "-")
        table.add_row(chain.name, desc, str(total), progress)

    console.print(table)
    console.print()


@chain_app.command("show")
def chain_show(
    name: str = typer.Argument(..., help="任务链名称"),
):
    """
    显示任务链详情

    示例:
        forge gamify chain show "北境迁移计划"
    """
    from habitica_forge.quest import get_chain_manager

    manager = get_chain_manager()
    chain = manager.get_chain(name)

    if not chain:
        print_error(f"任务链 '{name}' 不存在")
        raise typer.Exit(1)

    async def _run():
        async with HabiticaClient() as habitica_client:
            # 获取任务链中的所有任务
            tasks = []
            for task_id in chain.tasks:
                try:
                    task = await habitica_client.get_task(task_id)
                    tasks.append(task)
                except Exception as e:
                    logger.warning(f"Failed to get task {task_id}: {e}")

            # 渲染任务链信息
            console.print()
            console.print("[bold cyan]═══════════════════════════════════════════[/]")
            console.print(f"[bold cyan]    任务链: {chain.name}[/]")
            console.print("[bold cyan]═══════════════════════════════════════════[/]")

            if chain.description:
                console.print(f"\n[dim italic]{chain.description}[/]")

            # 进度条
            completed, total = chain.get_progress()
            console.print(f"\n{chain.render_progress_bar()}")

            # 任务列表
            console.print(f"\n[bold]任务列表 ({len(tasks)} 个):[/]\n")

            # 获取标签映射
            all_tags = await habitica_client.get_tags()
            id_to_name = {tag.id: tag.name for tag in all_tags}

            for i, task in enumerate(tasks, 1):
                index_display = f"[yellow]{i}[/]"
                status = "[green]✓[/]" if task.completed else "[dim]○[/]"
                chain_title = chain.render_chain_title(i)

                console.print(f"  {status} {index_display}. [bold]{chain_title}[/]")
                console.print(f"       [dim]{task.text[:40]}{'...' if len(task.text) > 40 else ''}[/]")

                # 显示 Forge 标签
                forge_tag_names = []
                for tag_id in task.tags:
                    tag_name = id_to_name.get(tag_id, "")
                    if any(tag_name.startswith(prefix.value) for prefix in ForgeTagPrefix):
                        forge_tag_names.append(tag_name)

                if forge_tag_names:
                    console.print(f"       [dim cyan]标签: {', '.join(forge_tag_names)}[/]")

            console.print("\n[bold cyan]═══════════════════════════════════════════[/]")
            console.print()

    try:
        asyncio.run(_run())
    except Exception as e:
        print_error(f"获取任务链详情失败: {e}")
        raise typer.Exit(1)


@chain_app.command("remove")
def chain_remove(
    name: str = typer.Argument(..., help="任务链名称"),
    task_id: Optional[str] = typer.Argument(None, help="任务编号或 ID（不指定则删除整个链）"),
    force: bool = typer.Option(False, "--force", "-f", help="跳过确认"),
):
    """
    从任务链移除任务或删除任务链

    示例:
        forge gamify chain remove "北境迁移计划" 1    # 移除指定任务
        forge gamify chain remove "北境迁移计划"      # 删除整个任务链
    """
    from habitica_forge.quest import get_chain_manager

    manager = get_chain_manager()
    chain = manager.get_chain(name)

    if not chain:
        print_error(f"任务链 '{name}' 不存在")
        raise typer.Exit(1)

    if task_id:
        # 移除单个任务
        resolved_id = _resolve_task_id(task_id)
        if chain.remove_task(resolved_id):
            manager.update_chain(chain)
            print_success(f"已从任务链 '{name}' 移除任务")
        else:
            print_warning(f"任务不在任务链 '{name}' 中")
    else:
        # 删除整个任务链
        if not force:
            try:
                confirm = input(f"确认删除任务链 '{name}'? [y/N]: ").strip().lower()
                if confirm not in ("y", "yes", "是"):
                    print_info("已取消")
                    return
            except (EOFError, KeyboardInterrupt):
                print_info("已取消")
                return

        manager.delete_chain(name)
        print_success(f"任务链 '{name}' 已删除")


@chain_app.command("complete")
def chain_complete(
    name: str = typer.Argument(..., help="任务链名称"),
):
    """
    标记任务链中的下一个任务为完成，并推进进度

    V2 阶段四增强：
    - 检测任务链完成状态
    - 完成任务链时给予额外奖励
    - 更高阶称号掉落概率

    示例:
        forge gamify chain complete "北境迁移计划"
    """
    from habitica_forge.quest import get_chain_manager

    manager = get_chain_manager()
    chain = manager.get_chain(name)

    if not chain:
        print_error(f"任务链 '{name}' 不存在")
        raise typer.Exit(1)

    async def _run():
        async with HabiticaClient() as habitica_client:
            # 获取当前任务
            current_task_id = chain.get_next_task()
            if not current_task_id:
                print_info("任务链已完成！")
                console.print("[bold green]🎉 恭喜完成整个任务链！[/]")
                return

            # 获取并完成当前任务
            task = await habitica_client.get_task(current_task_id)

            console.print(f"\n[bold]当前任务:[/] {task.text}")
            console.print(f"[dim]任务链进度: {chain.current_index + 1}/{len(chain.tasks)}[/]")

            try:
                confirm = input("\n确认完成此任务? [y/N]: ").strip().lower()
                if confirm not in ("y", "yes", "是"):
                    print_info("已取消")
                    return
            except (EOFError, KeyboardInterrupt):
                print_info("已取消")
                return

            # 完成任务
            await habitica_client.score_task(current_task_id, direction="up")

            # 推进任务链
            next_task_id = chain.advance()

            # 保存任务链状态（持久化）
            manager.update_chain(chain)

            # 清除缓存
            get_cache_manager().invalidate_all()

            print_success("任务已完成！")

            # 检查是否完成了整个任务链
            if next_task_id is None:
                # 任务链完成！给予额外奖励
                chain_length = len(chain.tasks)
                current_settings = get_settings()

                # 计算奖励详情
                bonus = calculate_chain_completion_bonus(chain_length, name)

                # 显示完成信息
                console.print()
                console.print("[bold cyan]═══════════════════════════════════════════[/]")
                console.print(f"[bold green]🎉 任务链「{name}」全部完成！[/]")
                console.print("[bold cyan]═══════════════════════════════════════════[/]")
                console.print()
                console.print(f"[bold yellow]{bonus['message']}[/]")
                console.print(f"[dim]任务链长度: {chain_length} 个任务[/]")
                console.print()

                # 触发任务链完成奖励
                dropped = trigger_chain_completion_reward(
                    task_id=current_task_id,
                    task_text=task.text,
                    chain_length=chain_length,
                    chain_name=name,
                    style=current_settings.forge_style,
                )

                if dropped:
                    console.print("[bold magenta]🌟 特殊称号掉落！正在后台生成...[/]")
                elif bonus["guaranteed_drop"]:
                    console.print("[bold magenta]🌟 稀有称号已触发！[/]")
                else:
                    console.print(f"[dim]称号掉落概率提升: x{bonus['bonus_multiplier']}[/]")

                console.print()
            else:
                next_task = await habitica_client.get_task(next_task_id)
                console.print(f"\n[bold cyan]下一个任务:[/] {next_task.text}")
                console.print(f"[dim]任务链进度: {chain.current_index + 1}/{len(chain.tasks)}[/]")

    try:
        asyncio.run(_run())
    except Exception as e:
        print_error(f"操作失败: {e}")
        raise typer.Exit(1)
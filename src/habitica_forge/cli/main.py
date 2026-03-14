"""CLI 主入口"""

import asyncio
from datetime import datetime
from typing import Optional

import typer

from habitica_forge import __version__
from habitica_forge.cli.commands import task_app
from habitica_forge.cli.header import print_header
from habitica_forge.cli.smart import smart_app
from habitica_forge.cli.viewer import (
    render_daily_list,
    render_habit_list,
    render_task_detail,
    render_task_list,
)
from habitica_forge.clients.habitica import HabiticaClient
from habitica_forge.core.bounty import (
    is_pending_wall_tag,
    make_active_tag_name,
    parse_wall_tags,
    trigger_bounty_drop,
)
from habitica_forge.core.cache import get_cache_manager
from habitica_forge.models import TaskData
from habitica_forge.utils.logger import console, get_logger, init_logging, print_error, print_success, print_info

logger = get_logger(__name__)

app = typer.Typer(
    name="forge",
    help="Habitica-Forge: 基于大语言模型的智能任务锻造 CLI 工具",
    no_args_is_help=True,
)

# 注册任务命令
app.add_typer(task_app, name="task")

# 注册智能拆解命令
app.add_typer(smart_app, name="smart")


def _init_app():
    """初始化应用（日志等）"""
    try:
        from habitica_forge.core.config import get_settings

        settings = get_settings()
        init_logging(level=settings.log_level)
    except Exception as e:
        # 配置加载失败时使用默认日志级别
        init_logging(level="INFO")
        print_error(f"配置加载失败: {e}")
        raise typer.Exit(1)


def _resolve_task_id(task_id_or_index: str) -> str:
    """
    解析任务 ID（支持编号或完整 ID）

    Args:
        task_id_or_index: 任务编号（如 "1"）或完整/部分 UUID

    Returns:
        完整的 UUID 字符串
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


def _resolve_checklist_item_id(task_id: str, item_id_or_index: str) -> str:
    """
    解析子任务 ID（支持编号或完整 ID）

    Args:
        task_id: 任务 ID
        item_id_or_index: 子任务编号（如 "1"）或完整 ID

    Returns:
        完整的子任务 ID 字符串
    """
    # 如果看起来像 ID（长度较长），直接返回
    if len(item_id_or_index) > 8:
        return item_id_or_index

    # 尝试作为编号查找
    cache_manager = get_cache_manager()
    item_id = cache_manager.index.get_checklist_item_id(task_id, item_id_or_index)

    if item_id:
        return item_id

    # 返回原值
    return item_id_or_index


# 不显示 Header 的命令列表
_SKIP_HEADER_COMMANDS = {"version", "init", "help", None}


def _check_and_spawn_scanner() -> None:
    """
    检查是否需要启动腐烂扫描器

    如果超过设定的扫描间隔时间未扫描，则在后台启动扫描器。
    """
    try:
        from habitica_forge.schedule.scanner import should_scan, spawn_background_scanner

        if should_scan():
            spawn_background_scanner()
    except Exception as e:
        # 扫描器启动失败不应该影响主功能
        logger.debug(f"Failed to check/spawn scanner: {e}")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Habitica-Forge CLI"""
    _init_app()

    # 检查是否需要显示 Header
    command_name = ctx.invoked_subcommand
    if command_name not in _SKIP_HEADER_COMMANDS:
        print_header()


# ============================================
# 基础命令
# ============================================


@app.command()
def version():
    """显示版本信息"""
    console.print(f"forge version {__version__}")


@app.command()
def init():
    """初始化配置（检查配置文件）"""
    _init_app()
    try:
        from habitica_forge.core.config import get_settings

        settings = get_settings()
        print_success("配置验证通过")
        console.print(f"  [label]Habitica User ID:[/] {settings.habitica_user_id[:8]}...")
        console.print(f"  [label]LLM Model:[/] {settings.llm_model}")
        console.print(f"  [label]Forge Style:[/] {settings.forge_style}")
    except Exception as e:
        print_error(f"配置验证失败: {e}")
        console.print("\n请确保 .env 文件存在且包含必要配置")
        console.print("参考 .env.example 文件进行配置")
        raise typer.Exit(1)


# ============================================
# 快捷命令（直接在根级别）
# ============================================


@app.command()
def list(
    task_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="任务类型: todos, dailys, habits, rewards"
    ),
    all_tasks: bool = typer.Option(False, "--all", "-a", help="显示所有类型所有状态的任务"),
):
    """
    显示任务列表（forge list 的快捷方式）

    示例:
        forge list              # 显示待办 Todo
        forge list -t todos     # 只显示 Todo
        forge list -t habits    # 只显示习惯
        forge list -t dailys    # 只显示每日任务
        forge list -t rewards   # 只显示奖励
        forge list --all        # 显示所有类型的任务
    """
    # 检查是否需要启动腐烂扫描器
    _check_and_spawn_scanner()

    async def _list():
        async with HabiticaClient() as client:
            # 获取任务
            tasks = await client.get_tasks()

            # 获取标签映射
            tags = await client.get_tags()
            tag_map = {tag.id: tag.name for tag in tags}

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
            elif task_type == "rewards":
                render_task_list(tasks, tag_map, title="奖励", show_completed=True)
            elif task_type == "todos":
                todos = [t for t in tasks if t.type == "todo"]
                render_task_list(todos, tag_map, title="待办任务", show_completed=True)
            elif all_tasks:
                # --all 显示所有类型的任务
                todos = [t for t in tasks if t.type == "todo"]
                habits = [t for t in tasks if t.type == "habit"]
                dailys = [t for t in tasks if t.type == "daily"]
                rewards = [t for t in tasks if t.type == "reward"]

                if todos:
                    render_task_list(todos, tag_map, title="待办任务", show_completed=True)
                if habits:
                    render_habit_list(habits, tag_map)
                if dailys:
                    render_daily_list(dailys, tag_map)
                if rewards:
                    render_task_list(rewards, tag_map, title="奖励", show_completed=True)

                if not any([todos, habits, dailys, rewards]):
                    console.print("[dim]没有任务[/dim]")
            else:
                # 默认只显示未完成的 Todo
                todos = [t for t in tasks if t.type == "todo"]
                render_task_list(todos, tag_map, title="待办任务", show_completed=False)

    try:
        asyncio.run(_list())
    except Exception as e:
        print_error(f"获取任务失败: {e}")
        raise typer.Exit(1)


@app.command()
def show(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
):
    """
    显示任务详情

    示例:
        forge show 1          # 通过编号查看
        forge show abc12345   # 通过部分 ID 查看
    """
    # 解析任务 ID
    resolved_id = _resolve_task_id(task_id)

    async def _show():
        async with HabiticaClient() as client:
            task = await client.get_task(resolved_id)
            tags = await client.get_tags()
            tag_map = {tag.id: tag.name for tag in tags}
            render_task_detail(task, tag_map)

    try:
        asyncio.run(_show())
    except Exception as e:
        print_error(f"获取任务详情失败: {e}")
        raise typer.Exit(1)


@app.command()
def add(
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
            get_cache_manager().invalidate_all()

            # 检查悬赏掉落
            from habitica_forge.core.config import get_settings
            current_settings = get_settings()
            dropped = trigger_bounty_drop(
                task_id=created.id,
                task_text=created.text,
                priority=priority_value,
                task_type="todo",
                style=current_settings.forge_style,
            )

            print_success(f"任务已创建: {created.id[:8]}")
            console.print(f"  [label]内容:[/] {created.text}")
            if created.notes:
                console.print(f"  [label]备注:[/] {created.notes}")

            if dropped:
                console.print()
                print_info("🌟 悬赏触发！正在后台生成称号...")

    try:
        asyncio.run(_add())
    except Exception as e:
        print_error(f"创建任务失败: {e}")
        raise typer.Exit(1)


@app.command()
def done(
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

    async def _complete():
        async with HabiticaClient() as client:
            # 先获取任务信息
            try:
                task = await client.get_task(resolved_id)
            except Exception:
                task = None

            # 完成任务
            await client.complete_task(resolved_id)

            # 清除缓存
            get_cache_manager().invalidate_all()

            task_text = task.text if task else task_id
            print_success(f"任务已完成: {task_text}")

            # 检查是否有待激活的称号
            if task:
                tags = await client.get_tags()
                tag_map = {t.id: t.name for t in tags}

                # 查找任务上是否有待激活称号
                for tag_id in task.tags:
                    tag_name = tag_map.get(tag_id, "")
                    if is_pending_wall_tag(tag_name):
                        # 提取称号名称
                        title_name = tag_name.replace("【WALL待激活】", "")
                        # 将标签重命名为激活状态
                        new_tag_name = make_active_tag_name(title_name)
                        await client.update_tag(tag_id, new_tag_name)
                        console.print()
                        print_info(f"🏆 称号解锁: [bold]{title_name}[/]")

    try:
        asyncio.run(_complete())
    except Exception as e:
        print_error(f"完成任务失败: {e}")
        raise typer.Exit(1)


@app.command()
def sync():
    """
    同步数据：清空本地缓存并从 Habitica 拉取最新数据

    示例:
        forge sync
    """

    async def _sync():
        async with HabiticaClient() as client:
            # 清空缓存
            cache_manager = get_cache_manager()
            cache_manager.clear_all()

            # 拉取最新数据
            with console.status("[bold cyan]正在同步数据...[/]"):
                tasks = await client.get_tasks()
                tags = await client.get_tags()

                # 更新缓存（使用 to_dict() 或 mode="json" 处理 datetime 序列化）
                cache_manager.tasks.set_tasks([t.to_dict() for t in tasks])
                cache_manager.tags.set_tags([t.model_dump(mode="json") for t in tags])

            print_success("数据同步完成")
            console.print(f"  [label]任务数:[/] {len(tasks)}")
            console.print(f"  [label]标签数:[/] {len(tags)}")

    try:
        asyncio.run(_sync())
    except Exception as e:
        print_error(f"同步失败: {e}")
        raise typer.Exit(1)


# ============================================
# 子任务快捷命令
# ============================================


@app.command("sub-add")
def sub_add(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
    text: str = typer.Argument(..., help="子任务内容"),
):
    """
    添加子任务

    示例:
        forge sub-add 1 "阅读文档"
        forge sub-add abc12345 "阅读文档"
    """
    # 解析任务 ID
    resolved_id = _resolve_task_id(task_id)

    async def _add():
        async with HabiticaClient() as client:
            await client.add_checklist_item(resolved_id, text)
            # 只清空任务缓存，保留索引缓存
            get_cache_manager().tasks.invalidate()
            print_success(f"子任务已添加: {text}")

    try:
        asyncio.run(_add())
    except Exception as e:
        print_error(f"添加子任务失败: {e}")
        raise typer.Exit(1)


@app.command("sub-done")
def sub_done(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
    item_id: str = typer.Argument(..., help="子任务编号或 ID"),
):
    """
    完成子任务

    示例:
        forge sub-done 1 1
        forge sub-done abc12345 xyz789
    """
    # 解析任务 ID
    resolved_task_id = _resolve_task_id(task_id)
    resolved_item_id = _resolve_checklist_item_id(resolved_task_id, item_id)

    async def _done():
        async with HabiticaClient() as client:
            await client.complete_checklist_item(resolved_task_id, resolved_item_id)
            # 只清空任务缓存，保留索引缓存
            get_cache_manager().tasks.invalidate()
            print_success(f"子任务已完成")

    try:
        asyncio.run(_done())
    except Exception as e:
        print_error(f"完成子任务失败: {e}")
        raise typer.Exit(1)


@app.command("sub-del")
def sub_del(
    task_id: str = typer.Argument(..., help="任务编号或 ID"),
    item_id: str = typer.Argument(..., help="子任务编号或 ID"),
):
    """
    删除子任务

    示例:
        forge sub-del 1 1
        forge sub-del abc12345 xyz789
    """
    # 解析任务 ID
    resolved_task_id = _resolve_task_id(task_id)
    resolved_item_id = _resolve_checklist_item_id(resolved_task_id, item_id)

    async def _delete():
        async with HabiticaClient() as client:
            await client.delete_checklist_item(resolved_task_id, resolved_item_id)
            # 只清空任务缓存，保留索引缓存
            get_cache_manager().tasks.invalidate()
            print_success(f"子任务已删除")

    try:
        asyncio.run(_delete())
    except Exception as e:
        print_error(f"删除子任务失败: {e}")
        raise typer.Exit(1)


# ============================================
# 称号系统命令
# ============================================


@app.command()
def wall():
    """
    显示成就墙（所有已解锁的称号）

    示例:
        forge wall
    """

    async def _wall():
        async with HabiticaClient() as client:
            tags = await client.get_tags()
            wall_tags = parse_wall_tags([{"id": t.id, "name": t.name} for t in tags])

            # 过滤只显示激活的称号（排除待激活）
            active_tags = [wt for wt in wall_tags if wt.status in ("active", "equipped")]

            if not active_tags:
                console.print("[dim]还没有解锁任何称号[/]")
                console.print()
                console.print("完成带有 [yellow]【WALL待激活】[/] 标签的任务来解锁称号！")
                return

            # 渲染成就墙
            console.print()
            console.print("[bold cyan]═══════════════════════════════════════[/]")
            console.print("[bold cyan]        🏆 成 就 墙 🏆                [/]")
            console.print("[bold cyan]═══════════════════════════════════════[/]")
            console.print()

            # 构建编号映射
            title_mapping = {}
            for idx, wt in enumerate(active_tags, start=1):
                index_str = str(idx)
                title_mapping[index_str] = {
                    "id": wt.id,
                    "title": wt.title,
                    "status": wt.status,
                }

                if wt.status == "equipped":
                    # 当前佩戴的称号
                    console.print(f"  [bold yellow]{index_str}. ★ {wt.title}[/] [dim](佩戴中)[/dim]")
                else:
                    console.print(f"  [yellow]{index_str}.[/] ○ {wt.title}")

            console.print()
            console.print(f"[dim]已解锁 {len(active_tags)} 个称号[/]")
            console.print()
            console.print("[dim]使用 [bold]forge switch <编号>[/] 来佩戴称号[/]")

            # 保存称号编号映射到缓存
            cache_manager = get_cache_manager()
            cache_manager.index.set_title_mapping(title_mapping)

    try:
        asyncio.run(_wall())
    except Exception as e:
        print_error(f"获取成就墙失败: {e}")
        raise typer.Exit(1)


@app.command()
def switch(
    title_ref: str = typer.Argument(..., help="称号编号或名称"),
):
    """
    佩戴称号

    将指定称号设为当前佩戴状态，会在命令行前缀显示。
    支持使用编号（先执行 forge wall 查看编号）或直接输入称号名。

    示例:
        forge switch 1           # 通过编号佩戴
        forge switch 星尘征服者   # 通过名称佩戴
    """

    async def _switch():
        async with HabiticaClient() as client:
            tags = await client.get_tags()
            wall_tags = parse_wall_tags([{"id": t.id, "name": t.name} for t in tags])

            # 查找匹配的称号
            target_tag = None
            current_equipped = None
            title_name = None

            # 首先尝试按编号查找
            cache_manager = get_cache_manager()
            title_info = cache_manager.index.get_title_info(title_ref)

            if title_info:
                # 通过编号找到称号
                title_name = title_info["title"]
                for wt in wall_tags:
                    if wt.status == "equipped":
                        current_equipped = wt
                    if wt.title == title_name and wt.status == "active":
                        target_tag = wt
                    elif wt.title == title_name and wt.status == "equipped":
                        # 已经是佩戴状态
                        print_info(f"称号 [bold]{title_name}[/] 已经在佩戴中")
                        return
            else:
                # 按名称查找
                title_name = title_ref
                for wt in wall_tags:
                    if wt.status == "equipped":
                        current_equipped = wt
                    if wt.title == title_name and wt.status == "active":
                        target_tag = wt
                    elif wt.title == title_name and wt.status == "equipped":
                        # 已经是佩戴状态
                        print_info(f"称号 [bold]{title_name}[/] 已经在佩戴中")
                        return

            if not target_tag:
                # 检查是否存在但未激活
                pending = [wt for wt in wall_tags if wt.title == title_name and wt.status == "pending"]
                if pending:
                    print_error(f"称号 [bold]{title_name}[/] 尚未激活，请先完成对应任务")
                else:
                    print_error(f"未找到称号: [bold]{title_ref}[/]")
                    console.print()
                    console.print("使用 [bold]forge wall[/] 查看所有可用称号及编号")
                raise typer.Exit(1)

            # 取消当前佩戴的称号
            if current_equipped:
                new_name = make_active_tag_name(current_equipped.title, equipped=False)
                await client.update_tag(current_equipped.id, new_name)

            # 佩戴新称号
            new_name = make_active_tag_name(target_tag.title, equipped=True)
            await client.update_tag(target_tag.id, new_name)

            # 清除缓存
            get_cache_manager().invalidate_all()

            print_success(f"已佩戴称号: [bold]{target_tag.title}[/]")

    try:
        asyncio.run(_switch())
    except Exception as e:
        print_error(f"佩戴称号失败: {e}")
        raise typer.Exit(1)


# ============================================
# 智能拆解快捷命令
# ============================================


@app.command("smart-task")
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
        forge smart-task 1           # 拆解编号为 1 的任务
        forge smart-task abc12345    # 拆解指定 ID 的任务
        forge smart-task 1 --keep    # 保留现有子任务
    """
    from habitica_forge.cli.smart import smart_task as _smart_task_impl
    _smart_task_impl(task_id, keep_existing)


@app.command("smart-add")
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
        forge smart-add "完成项目报告"
        forge smart-add "学习新技术" -n "重要技能"
        forge smart-add "简单任务" --no-decompose
    """
    from habitica_forge.cli.smart import smart_add as _smart_add_impl
    _smart_add_impl(text, notes, no_decompose)


if __name__ == "__main__":
    app()
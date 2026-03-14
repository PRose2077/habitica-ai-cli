"""任务展示模块"""

from datetime import datetime
from typing import Dict, List, Optional

from rich.progress import Progress
from rich.table import Table

from habitica_forge.core.bounty import is_equipped_wall_tag, extract_title_name
from habitica_forge.core.cache import get_cache_manager
from habitica_forge.models import TaskData
from habitica_forge.utils.logger import console, print_panel, print_title

# 优先级映射
PRIORITY_LABELS = {
    0.1: (" trivial ", "dim"),
    1.0: ("  easy   ", "green"),
    1.5: (" medium  ", "yellow"),
    2.0: ("  hard   ", "red bold"),
}

# 任务类型图标
TYPE_ICONS = {
    "todo": " ",
    "daily": " ",
    "habit": " ",
    "reward": " ",
}


def get_priority_label(priority: float) -> tuple[str, str]:
    """获取优先级标签"""
    return PRIORITY_LABELS.get(priority, ("  ?   ", "dim"))


def format_date(date: Optional[datetime]) -> str:
    """格式化日期"""
    if date is None:
        return ""

    # 确保时区一致
    now = datetime.now(date.tzinfo) if date.tzinfo else datetime.now()

    # 只比较日期部分
    today = now.date()
    target_date = date.date()
    delta_days = (target_date - today).days

    if delta_days < 0:
        return f"[red]{date.strftime('%m-%d')}[/red]"
    elif delta_days == 0:
        return f"[yellow]今天[/yellow]"
    elif delta_days == 1:
        return f"[green]明天[/green]"
    elif delta_days <= 7:
        return f"{delta_days}天后"
    else:
        return date.strftime("%m-%d")


def render_checklist_progress(checklist: list, completed: bool = False) -> str:
    """渲染 Checklist 进度条"""
    if not checklist:
        return ""

    if completed:
        return "[green] 100%[/green]"

    done = sum(1 for item in checklist if item.completed)
    total = len(checklist)
    percent = int(done / total * 100) if total > 0 else 0

    # 使用进度条样式
    bar_width = 8
    filled = int(bar_width * done / total) if total > 0 else 0
    bar = "=" * filled + "-" * (bar_width - filled)

    if percent == 100:
        return f"[green]{bar} {done}/{total}[/green]"
    elif percent >= 50:
        return f"[yellow]{bar} {done}/{total}[/yellow]"
    else:
        return f"[dim]{bar} {done}/{total}[/dim]"


def truncate_text(text: str, max_length: int = 40) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def get_equipped_title_from_tags(tag_map: Dict[str, str]) -> Optional[str]:
    """
    从标签映射中提取当前佩戴的称号

    Args:
        tag_map: 标签 ID 到名称的映射

    Returns:
        当前佩戴的称号名称，如果没有则返回 None
    """
    for tag_id, tag_name in tag_map.items():
        if is_equipped_wall_tag(tag_name):
            return extract_title_name(tag_name)
    return None


def render_task_list(
    tasks: List[TaskData],
    tag_map: Dict[str, str],
    title: str = "任务列表",
    show_completed: bool = False,
) -> None:
    """
    渲染任务列表表格

    Args:
        tasks: 任务列表
        tag_map: 标签 ID 到名称的映射
        title: 表格标题
        show_completed: 是否显示已完成的任务
    """
    if not tasks:
        console.print(f"[dim]没有{title}[/dim]")
        return

    # 从标签映射中获取当前佩戴的称号，显示在表头
    equipped_title = get_equipped_title_from_tags(tag_map)
    if equipped_title:
        title = f"[magenta]【{equipped_title}】[/] {title}"

    table = Table(
        title=title,
        show_header=True,
        header_style="bold cyan",
        show_edge=True,
        expand=True,
    )

    # 表头 - 添加编号列
    table.add_column("No.", style="bold yellow", width=4, justify="center")
    table.add_column("状态", width=6, justify="center")
    table.add_column("任务", min_width=30)
    table.add_column("难度", width=10, justify="center")
    table.add_column("进度", width=14, justify="center")
    table.add_column("日期", width=10, justify="center")

    # 构建编号映射并保存到缓存
    index_mapping = {}

    for idx, task in enumerate(tasks, start=1):
        # 跳过已完成的任务（除非指定显示）
        if task.completed and not show_completed:
            continue

        # 编号
        index_str = str(idx)
        index_mapping[index_str] = task.id

        # 状态
        if task.completed:
            status = "[green]  [/green]"
        elif task.type == "habit":
            status = "[cyan]  [/cyan]"
        elif task.type == "daily":
            status = "[blue]  [/blue]"
        else:
            status = "[dim]  [/dim]"

        # 任务名称
        task_text = truncate_text(task.text, 50)

        # 难度
        priority_label, priority_style = get_priority_label(task.priority)
        priority_display = f"[{priority_style}]{priority_label}[/]"

        # 进度
        progress = render_checklist_progress(task.checklist, task.completed)

        # 日期
        date_str = format_date(task.date)

        table.add_row(
            index_str,
            status,
            task_text,
            priority_display,
            progress,
            date_str,
        )

    console.print(table)

    # 保存编号映射到缓存
    cache_manager = get_cache_manager()
    cache_manager.index.set_mapping(index_mapping)


def render_task_detail(task: TaskData, tag_map: Dict[str, str]) -> None:
    """
    渲染单个任务详情

    Args:
        task: 任务数据
        tag_map: 标签 ID 到名称的映射
    """
    # 标题
    title_icon = "  " if task.completed else "  "
    title_style = "dim" if task.completed else "title"
    console.print(f"\n[{title_style}]{title_icon} {task.text}[/]\n")

    # 基本信息
    info_table = Table(show_header=False, box=None, expand=True)
    info_table.add_column("Key", style="label", width=12)
    info_table.add_column("Value")

    # ID
    info_table.add_row("ID", task.id or "?")

    # 类型
    type_names = {"todo": "待办", "daily": "每日", "habit": "习惯", "reward": "奖励"}
    info_table.add_row("类型", type_names.get(task.type, task.type))

    # 难度
    priority_label, priority_style = get_priority_label(task.priority)
    info_table.add_row("难度", f"[{priority_style}]{priority_label}[/]")

    # 状态
    status = "[green]已完成[/]" if task.completed else "[yellow]进行中[/]"
    info_table.add_row("状态", status)

    # 日期
    if task.date:
        info_table.add_row("截止日期", format_date(task.date))

    # 标签
    if task.tags:
        tag_names = [tag_map.get(tid, tid[:8]) for tid in task.tags]
        info_table.add_row("标签", ", ".join(tag_names))

    console.print(info_table)

    # 备注
    if task.notes:
        console.print(f"\n[label]备注:[/]")
        console.print(f"  {task.notes}")

    # Checklist
    if task.checklist:
        console.print(f"\n[label]子任务 ({len(task.checklist)}):[/]")
        # 构建子任务编号映射
        checklist_mapping = {}
        for i, item in enumerate(task.checklist, 1):
            index_str = str(i)
            if item.id:
                checklist_mapping[index_str] = item.id
            checkbox = "[green]  [/]" if item.completed else "[dim]  [/]"
            if item.completed:
                console.print(f"  [yellow]{index_str}[/]. {checkbox} [dim]{item.text}[/dim]")
            else:
                console.print(f"  [yellow]{index_str}[/]. {checkbox} {item.text}")
        # 保存子任务编号映射到缓存
        if checklist_mapping:
            cache_manager = get_cache_manager()
            cache_manager.index.set_checklist_mapping(task.id, checklist_mapping)

    console.print()


def render_habit_list(
    tasks: List[TaskData],
    tag_map: Dict[str, str],
) -> None:
    """渲染习惯列表"""
    habits = [t for t in tasks if t.type == "habit"]

    if not habits:
        console.print("[dim]没有习惯任务[/dim]")
        return

    # 从标签映射中获取当前佩戴的称号，显示在表头
    equipped_title = get_equipped_title_from_tags(tag_map)
    title = "习惯"
    if equipped_title:
        title = f"[magenta]【{equipped_title}】[/] {title}"

    table = Table(
        title=title,
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )

    # 添加编号列
    table.add_column("No.", style="bold yellow", width=4, justify="center")
    table.add_column("习惯", min_width=30)
    table.add_column("+", width=4, justify="center")
    table.add_column("-", width=4, justify="center")
    table.add_column("难度", width=10, justify="center")

    # 构建编号映射
    index_mapping = {}

    for idx, task in enumerate(habits, start=1):
        index_str = str(idx)
        index_mapping[index_str] = task.id

        up_btn = "[green]  [/]" if task.up else "[dim]  [/]"
        down_btn = "[red]  [/]" if task.down else "[dim]  [/]"

        priority_label, priority_style = get_priority_label(task.priority)
        priority_display = f"[{priority_style}]{priority_label}[/]"

        table.add_row(
            index_str,
            truncate_text(task.text, 40),
            up_btn,
            down_btn,
            priority_display,
        )

    console.print(table)

    # 保存编号映射到缓存
    cache_manager = get_cache_manager()
    cache_manager.index.set_mapping(index_mapping)


def render_daily_list(
    tasks: List[TaskData],
    tag_map: Dict[str, str],
) -> None:
    """渲染每日任务列表"""
    dailys = [t for t in tasks if t.type == "daily"]

    if not dailys:
        console.print("[dim]没有每日任务[/dim]")
        return

    # 从标签映射中获取当前佩戴的称号，显示在表头
    equipped_title = get_equipped_title_from_tags(tag_map)
    title = "每日任务"
    if equipped_title:
        title = f"[magenta]【{equipped_title}】[/] {title}"

    table = Table(
        title=title,
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )

    # 添加编号列
    table.add_column("No.", style="bold yellow", width=4, justify="center")
    table.add_column("状态", width=6, justify="center")
    table.add_column("任务", min_width=30)
    table.add_column("连击", width=6, justify="center")
    table.add_column("进度", width=14, justify="center")

    # 构建编号映射
    index_mapping = {}

    for idx, task in enumerate(dailys, start=1):
        index_str = str(idx)
        index_mapping[index_str] = task.id

        # 状态 - 每日任务有完成状态
        status = "[green]  [/]" if task.completed else "[dim]  [/]"

        # 连击
        streak = task.streak
        if streak >= 21:
            streak_display = f"[bold green]{streak}[/]"
        elif streak >= 7:
            streak_display = f"[yellow]{streak}[/]"
        elif streak > 0:
            streak_display = f"[dim]{streak}[/]"
        else:
            streak_display = "[dim]-[/]"

        # 进度
        progress = render_checklist_progress(task.checklist, task.completed)

        table.add_row(
            index_str,
            status,
            truncate_text(task.text, 40),
            streak_display,
            progress,
        )

    console.print(table)

    # 保存编号映射到缓存
    cache_manager = get_cache_manager()
    cache_manager.index.set_mapping(index_mapping)
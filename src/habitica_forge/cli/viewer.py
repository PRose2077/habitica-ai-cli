"""任务展示模块

V2 阶段四增强：
- 支持传奇任务信息展示
- 支持章节进度展示
- 支持任务链信息展示

V2 阶段五增强：
- 支持地点系统展示
- 支持职业倾向显示
- 支持 emoji 图标系统
- 使用 Tags 替代元数据存储
"""

from datetime import datetime
from typing import Dict, List, Optional, Set

from rich.progress import Progress
from rich.table import Table

from habitica_forge.core.bounty import is_equipped_wall_tag, extract_title_name
from habitica_forge.core.cache import get_cache_manager
from habitica_forge.models import TaskData
from habitica_forge.quest.tags import (
    ForgeTagPrefix,
    parse_forge_tags,
    LEGENDARY_TAG,
)
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

# V2 阶段五：任务原型图标 (emoji)
ARCHETYPE_ICONS = {
    "cleanup": "🧹",    # 清理
    "repair": "🔧",     # 修复
    "explore": "🔍",    # 探索
    "craft": "⚒️",      # 制作
    "communicate": "📨", # 沟通
    "learn": "📚",      # 学习
    "battle": "⚔️",     # 战斗
    "supply": "🎒",     # 补给
    None: "📋",         # 默认
}

# V2 阶段五：传奇任务类型图标
LEGENDARY_ICONS = {
    "main": "👑",       # 主线
    "expedition": "🗺️", # 远征
    "campaign": "🎯",   # 战役
    "escort": "🛡️",     # 护送
    "saga": "📜",       # 史诗
    "chain": "🔗",      # 任务链
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


def get_archetype_icon(archetype: Optional[str]) -> str:
    """获取任务原型图标

    Args:
        archetype: 任务原型

    Returns:
        emoji 图标
    """
    return ARCHETYPE_ICONS.get(archetype, ARCHETYPE_ICONS[None])


def get_legendary_icon(legendary_type: Optional[str]) -> str:
    """获取传奇任务类型图标

    Args:
        legendary_type: 传奇任务类型

    Returns:
        emoji 图标
    """
    return LEGENDARY_ICONS.get(legendary_type, "⭐")


def get_forge_info_from_tags(
    task: TaskData,
    tag_map: Dict[str, str],
) -> Dict[str, Optional[str]]:
    """从任务的标签中提取 Forge 信息

    Args:
        task: 任务数据
        tag_map: 标签 ID 到名称的映射

    Returns:
        Forge 信息字典
    """
    tag_names = [tag_map.get(tid, "") for tid in task.tags]
    return parse_forge_tags(tag_names)


def get_non_forge_tag_names(
    task: TaskData,
    tag_map: Dict[str, str],
) -> List[str]:
    """获取任务的非 Forge 标签名称（用于展示）

    排除 Forge 相关标签和称号标签。

    Args:
        task: 任务数据
        tag_map: 标签 ID 到名称的映射

    Returns:
        非 Forge 标签名称列表
    """
    non_forge_tags = []
    for tag_id in task.tags:
        tag_name = tag_map.get(tag_id, "")
        # 排除 Forge 相关标签
        if any(tag_name.startswith(prefix.value) for prefix in ForgeTagPrefix):
            continue
        # 排除称号标签（以 "【" 和 "】" 包裹的，或者以 "称号:" 开头的）
        if is_equipped_wall_tag(tag_name):
            continue
        non_forge_tags.append(tag_name)
    return non_forge_tags


def render_profession_header(
    equipped_title: Optional[str],
    profession_name: Optional[str] = None,
) -> str:
    """渲染职业倾向和称号的 header

    Args:
        equipped_title: 当前佩戴的称号
        profession_name: 职业倾向名称

    Returns:
        渲染后的标题字符串
    """
    parts = []

    if equipped_title:
        parts.append(f"[magenta]【{equipped_title}】[/]")

    if profession_name:
        parts.append(f"[cyan]「{profession_name}」[/]")

    return " ".join(parts) if parts else ""


def render_task_list(
    tasks: List[TaskData],
    tag_map: Dict[str, str],
    title: str = "任务列表",
    show_completed: bool = False,
    prefer_gamified: bool = True,
    show_icons: bool = True,
    show_location: bool = False,
    show_tags: bool = True,
) -> None:
    """
    渲染任务列表表格

    V2 阶段四增强：
    - 支持游戏化标题显示
    - 支持传奇任务前缀显示
    - 支持任务链徽章

    V2 阶段五增强：
    - 支持 emoji 图标显示
    - 支持地点列显示
    - 使用 Tags 替代元数据
    - 支持标签列显示（排除称号标签）

    Args:
        tasks: 任务列表
        tag_map: 标签 ID 到名称的映射
        title: 表格标题
        show_completed: 是否显示已完成的任务
        prefer_gamified: 是否优先显示游戏化标题
        show_icons: 是否显示图标
        show_location: 是否显示地点列
        show_tags: 是否显示标签列
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
    table.add_column("状态", width=4, justify="center")
    if show_icons:
        table.add_column("", width=2, justify="center")  # 图标列
    table.add_column("任务", min_width=20)
    if show_location:
        table.add_column("地点", width=8, justify="center")
    if show_tags:
        table.add_column("标签", width=12, justify="left")
    table.add_column("难度", width=10, justify="center")
    table.add_column("进度", width=12, justify="center")
    table.add_column("日期", width=8, justify="center")

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
            status = "[green]✓[/]"
        elif task.type == "habit":
            status = "[cyan]○[/]"
        elif task.type == "daily":
            status = "[blue]◇[/]"
        else:
            status = "[dim]○[/]"

        # 从 tags 获取 Forge 信息
        forge_info = get_forge_info_from_tags(task, tag_map)

        # 图标 - V2 阶段五
        icon = ""
        if show_icons:
            if forge_info.get("is_legendary") and forge_info.get("legendary_type"):
                icon = get_legendary_icon(forge_info["legendary_type"])
            elif forge_info.get("archetype"):
                icon = get_archetype_icon(forge_info["archetype"])
            if not icon:
                icon = get_archetype_icon(None)

        # 任务名称
        display_text = task.text
        task_text = truncate_text(display_text, 35)

        # 地点 - V2 阶段五
        location_display = ""
        if show_location and forge_info.get("location"):
            location_display = f"[green]{forge_info['location'][:6]}[/]"

        # 标签列（排除 Forge 标签和称号标签）
        tags_display = ""
        if show_tags:
            non_forge_tags = get_non_forge_tag_names(task, tag_map)
            if non_forge_tags:
                # 最多显示2个标签
                tag_str = ", ".join(non_forge_tags[:2])
                if len(non_forge_tags) > 2:
                    tag_str += "..."
                tags_display = f"[dim]{tag_str}[/]"

        # 难度
        priority_label, priority_style = get_priority_label(task.priority)
        priority_display = f"[{priority_style}]{priority_label}[/]"

        # 进度
        progress = render_checklist_progress(task.checklist, task.completed)

        # 日期
        date_str = format_date(task.date)

        # 构建行
        row = [index_str, status]
        if show_icons:
            row.append(icon)
        row.append(task_text)
        if show_location:
            row.append(location_display)
        if show_tags:
            row.append(tags_display)
        row.extend([priority_display, progress, date_str])

        table.add_row(*row)

    console.print(table)

    # 保存编号映射到缓存
    cache_manager = get_cache_manager()
    cache_manager.index.set_mapping(index_mapping)


def render_task_detail(task: TaskData, tag_map: Dict[str, str]) -> None:
    """
    渲染单个任务详情

    V2 阶段四增强：
    - 展示传奇任务类型和前缀
    - 展示章节进度（阶段化子任务）
    - 展示任务链信息

    V2 阶段五增强：
    - 展示图标
    - 增强地点展示
    - 使用 Tags 替代元数据

    Args:
        task: 任务数据
        tag_map: 标签 ID 到名称的映射
    """
    # 从 tags 获取 Forge 信息
    forge_info = get_forge_info_from_tags(task, tag_map)

    # 标题
    title_text = task.text

    # 图标
    icon = ""
    if forge_info.get("is_legendary") and forge_info.get("legendary_type"):
        icon = get_legendary_icon(forge_info["legendary_type"])
    elif forge_info.get("archetype"):
        icon = get_archetype_icon(forge_info["archetype"])

    title_icon_display = "✓" if task.completed else icon
    title_style = "dim" if task.completed else "title"
    console.print(f"\n[{title_style}]{title_icon_display} {title_text}[/]\n")

    # 任务链徽章
    if forge_info.get("chain_name"):
        console.print(f"  [bold purple]【{forge_info['chain_name']}】[/]\n")

    # 传奇任务标签
    if forge_info.get("is_legendary"):
        legendary_labels = {
            "main": "[bold green]【主线任务】[/]",
            "expedition": "[bold cyan]【远征任务】[/]",
            "campaign": "[bold yellow]【战役任务】[/]",
            "escort": "[bold white]【护送任务】[/]",
            "saga": "[bold red]【史诗任务】[/]",
            "chain": "[bold purple]【任务链】[/]",
        }
        label = legendary_labels.get(
            forge_info.get("legendary_type"),
            "[bold magenta]【传奇任务】[/]"
        )
        console.print(f"  {label}\n")

    # 基本信息
    info_table = Table(show_header=False, box=None, expand=True)
    info_table.add_column("Key", style="label", width=12)
    info_table.add_column("Value")

    # ID
    info_table.add_row("ID", task.id or "?")

    # 类型
    type_names = {"todo": "待办", "daily": "每日", "habit": "习惯", "reward": "奖励"}
    info_table.add_row("类型", type_names.get(task.type, task.type))

    # 任务原型（带图标）
    if forge_info.get("archetype"):
        archetype_names = {
            "cleanup": "清理", "repair": "修复", "explore": "探索",
            "craft": "制作", "communicate": "沟通", "learn": "学习",
            "battle": "战斗", "supply": "补给",
        }
        archetype_display = archetype_names.get(forge_info["archetype"], forge_info["archetype"])
        archetype_icon = get_archetype_icon(forge_info["archetype"])
        info_table.add_row("原型", f"{archetype_icon} [cyan]{archetype_display}[/]")

    # 地点
    if forge_info.get("location"):
        info_table.add_row("地点", f"📍 [green]{forge_info['location']}[/]")

    # 难度
    priority_label, priority_style = get_priority_label(task.priority)
    info_table.add_row("难度", f"[{priority_style}]{priority_label}[/]")

    # 状态
    status = "[green]已完成[/]" if task.completed else "[yellow]进行中[/]"
    info_table.add_row("状态", status)

    # 日期
    if task.date:
        info_table.add_row("截止日期", format_date(task.date))

    # 标签（排除 Forge 标签和称号标签）
    non_forge_tags = get_non_forge_tag_names(task, tag_map)
    if non_forge_tags:
        info_table.add_row("标签", ", ".join(non_forge_tags))

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
            checkbox = "[green]✓[/]" if item.completed else "[dim]○[/]"
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
"""全局身份标识 Header 组件

在每个命令输出前渲染统一页眉，显示：
- 当前佩戴称号
- 用户 ID（部分显示）
- 系统状态
"""

from typing import Optional, Tuple

from habitica_forge.core.bounty import extract_title_name, is_equipped_wall_tag
from habitica_forge.core.cache import get_cache_manager
from habitica_forge.core.config import get_settings
from habitica_forge.utils.logger import console, get_logger

logger = get_logger(__name__)

# 腐烂状态前缀（根据未处理腐烂任务数量动态变化）
CORRUPTION_PREFIXES = [
    ("", 0),          # 无腐烂任务
    ("[italic]迟疑的[/] ", 1),      # 1-2 个腐烂任务
    ("[italic]焦虑的[/] ", 3),      # 3-5 个腐烂任务
    ("[bold red]走火入魔的[/] ", 6),  # 6+ 个腐烂任务
]


def get_current_identity() -> Tuple[Optional[str], bool]:
    """
    从本地缓存中获取当前佩戴的称号

    Returns:
        (称号名称, 是否有效缓存)
        如果没有佩戴称号，返回 (None, 是否有效缓存)
    """
    cache_manager = get_cache_manager()
    tags = cache_manager.tags.get_tags()

    if tags is None:
        # 缓存无效，需要同步
        return None, False

    for tag in tags:
        tag_name = tag.get("name", "")
        if is_equipped_wall_tag(tag_name):
            return extract_title_name(tag_name), True

    return None, True


def get_user_display_id() -> str:
    """获取用户 ID 的简短显示形式"""
    try:
        settings = get_settings()
        user_id = settings.habitica_user_id
        if user_id:
            return f"{user_id[:8]}..."
    except Exception:
        pass
    return "Unknown"


def get_corruption_prefix(corrupted_count: int = 0) -> str:
    """
    根据腐烂任务数量获取称号前缀

    Args:
        corrupted_count: 腐烂任务数量

    Returns:
        称号前缀字符串（可能包含 Rich 标签）
    """
    for prefix, threshold in reversed(CORRUPTION_PREFIXES):
        if corrupted_count >= threshold:
            return prefix
    return ""


def render_identity_header(
    title: Optional[str] = None,
    corrupted_count: int = 0,
    status: str = "就绪",
) -> None:
    """
    渲染身份标识 Header

    Args:
        title: 称号名称（如果为 None 则自动从缓存获取）
        corrupted_count: 腐烂任务数量（用于动态前缀）
        status: 系统状态显示
    """
    try:
        # 获取称号
        if title is None:
            identity, cache_valid = get_current_identity()
        else:
            identity, cache_valid = title, True

        # 获取用户 ID
        user_id = get_user_display_id()

        # 构建内容
        content_parts = []

        # 用户 ID
        content_parts.append(f"[dim]ID:[/] [cyan]{user_id}[/]")

        # 称号
        if identity:
            corruption_prefix = get_corruption_prefix(corrupted_count)
            content_parts.append(f"[dim]称号:[/] [magenta]{corruption_prefix}【{identity}】[/]")
        else:
            content_parts.append("[dim]称号:[/] [dim]未佩戴[/]")

        # 系统状态
        status_color = "green" if status == "就绪" else "yellow"
        if not cache_valid:
            status = "离线"
            status_color = "dim"
        content_parts.append(f"[dim]状态:[/] [{status_color}]{status}[/]")

        # 渲染简化版 Header（单行，用 | 分隔）
        header_text = "  |  ".join(content_parts)
        console.print()
        console.print(header_text)
        console.print()

    except Exception as e:
        # 如果渲染失败，输出简化的 Header
        logger.warning(f"Header rendering failed: {e}")
        console.print(f"[dim]ID: {get_user_display_id()}[/]")
        console.print()


def render_compact_header(
    title: Optional[str] = None,
    corrupted_count: int = 0,
) -> str:
    """
    渲染紧凑型 Header（单行文本，用于表格标题等）

    Args:
        title: 称号名称
        corrupted_count: 腐烂任务数量

    Returns:
        Rich 格式的字符串
    """
    if title is None:
        identity, _ = get_current_identity()
    else:
        identity = title

    if identity:
        corruption_prefix = get_corruption_prefix(corrupted_count)
        return f"[magenta]{corruption_prefix}【{identity}】[/]"

    return ""


# ============================================
# 便捷函数
# ============================================


def print_header(
    show_title: bool = True,
    status: str = "就绪",
) -> None:
    """
    打印标准 Header（便捷函数）

    Args:
        show_title: 是否显示称号
        status: 系统状态
    """
    if show_title:
        render_identity_header(status=status)
    else:
        # 只显示简化版本
        user_id = get_user_display_id()
        console.print(f"[dim]ID: {user_id}[/] | [dim]状态: {status}[/]")
        console.print()
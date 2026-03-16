"""风格管理模块

统一风格解析逻辑，支持动态切换风格。
"""

from pathlib import Path
from typing import Optional

from habitica_forge.styles import (
    get_all_style_configs,
    get_style_config,
    get_style_display_name,
    normalize_style,
)
from habitica_forge.utils.logger import get_logger

logger = get_logger(__name__)

# 风格配置缓存文件路径
STYLE_CONFIG_FILE = Path.home() / ".config" / "habitica-forge" / "style.json"


def find_env_file() -> Path:
    """
    查找 .env 文件路径

    按以下顺序查找：
    1. 当前工作目录
    2. 项目根目录（通过 pyproject.toml 定位）

    Returns:
        .env 文件路径
    """
    # 首先检查当前工作目录
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        return cwd_env

    # 查找项目根目录（通过 pyproject.toml 定位）
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            project_env = parent / ".env"
            if project_env.exists():
                return project_env
            # 如果项目根目录存在但 .env 不存在，返回项目根目录的 .env 路径
            return project_env

    # 默认返回当前工作目录
    return cwd_env


def get_current_style() -> str:
    """
    获取当前风格

    优先从运行时配置读取，否则从环境变量读取。

    Returns:
        当前风格名称
    """
    from habitica_forge.core.config import get_settings
    settings = get_settings()
    return normalize_style(settings.forge_style)


def get_available_styles() -> list[str]:
    """
    获取所有可用风格名称

    从 styles/ 目录的 YAML 配置文件动态读取。

    Returns:
        风格名称列表
    """
    configs = get_all_style_configs()
    return [c.name for c in configs]


def get_all_styles() -> list[dict]:
    """
    获取所有可用风格

    Returns:
        风格列表，每项包含 name, display_name, description
    """
    configs = get_all_style_configs()
    return [
        {
            "name": config.name,
            "display_name": config.display_name,
            "description": config.description,
        }
        for config in configs
    ]


def set_style(style: str) -> bool:
    """
    设置风格

    更新 .env 文件中的 FORGE_STYLE 配置。

    Args:
        style: 风格名称

    Returns:
        是否成功
    """
    # 标准化风格名称
    normalized = normalize_style(style)

    available = get_available_styles()
    if normalized not in available:
        logger.warning(f"Unknown style: {style}, fallback to normal")
        normalized = "normal"

    try:
        # 获取 .env 文件路径
        env_file = find_env_file()

        if env_file.exists():
            # 读取现有内容
            with open(env_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # 更新或添加 FORGE_STYLE
            found = False
            for i, line in enumerate(lines):
                if line.strip().startswith("FORGE_STYLE="):
                    lines[i] = f"FORGE_STYLE={normalized}\n"
                    found = True
                    break

            if not found:
                # 添加新行
                lines.append(f"\nFORGE_STYLE={normalized}\n")

            # 写回文件
            with open(env_file, "w", encoding="utf-8") as f:
                f.writelines(lines)
        else:
            # 创建新的 .env 文件
            with open(env_file, "w", encoding="utf-8") as f:
                f.write(f"FORGE_STYLE={normalized}\n")

        # 清除配置缓存
        from habitica_forge.core.config import get_settings
        get_settings.cache_clear()

        logger.info(f"Style set to: {normalized}")
        return True

    except Exception as e:
        logger.error(f"Failed to set style: {e}")
        return False


def is_gamified_style(style: Optional[str] = None) -> bool:
    """
    检查当前风格是否为游戏化风格

    Args:
        style: 风格名称，默认使用当前风格

    Returns:
        是否为游戏化风格（非 normal）
    """
    if style is None:
        style = get_current_style()
    else:
        style = normalize_style(style)

    return style != "normal"
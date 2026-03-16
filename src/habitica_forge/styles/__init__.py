"""风格配置模块

统一管理所有游戏风格的提示词配置。
只需在 styles/ 目录下添加 YAML 文件即可新增风格。
"""

from habitica_forge.styles.loader import (
    StyleConfig,
    get_style_config,
    get_all_style_configs,
    get_all_style_names,
    get_style_display_name,
    get_style_description,
    get_style_case_map,
    normalize_style,
    reload_styles,
)

__all__ = [
    "StyleConfig",
    "get_style_config",
    "get_all_style_configs",
    "get_all_style_names",
    "get_style_display_name",
    "get_style_description",
    "get_style_case_map",
    "normalize_style",
    "reload_styles",
]
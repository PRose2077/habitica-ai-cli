"""风格配置模块

统一管理所有游戏风格的提示词配置。
只需在 styles/ 目录下添加 YAML 文件即可新增风格。

V2 新增：
- 世界观词典系统 (Lexicon)
- 任务类型命名模板 (Templates)
- 任务上下文词典 (Context)
- 图片资源管理 (Images)
"""

from habitica_forge.styles.loader import (
    # 核心类
    StyleConfig,
    Lexicon,
    StyleTemplates,
    ContextDictionary,
    QualityBaseline,
    PromptConfig,
    # 风格查询
    get_style_config,
    get_all_style_configs,
    get_all_style_names,
    get_style_display_name,
    get_style_description,
    get_style_case_map,
    normalize_style,
    reload_styles,
)

from habitica_forge.styles.images import (
    # 图片资源
    ImageResource,
    get_image_by_id,
    get_image_url,
    get_images_for_style,
    get_images_for_archetype,
    get_images_for_usage,
    get_ai_visible_images,
    render_image_markdown,
    reload_images,
)

__all__ = [
    # 风格配置
    "StyleConfig",
    "Lexicon",
    "StyleTemplates",
    "ContextDictionary",
    "QualityBaseline",
    "PromptConfig",
    # 风格查询
    "get_style_config",
    "get_all_style_configs",
    "get_all_style_names",
    "get_style_display_name",
    "get_style_description",
    "get_style_case_map",
    "normalize_style",
    "reload_styles",
    # 图片资源
    "ImageResource",
    "get_image_by_id",
    "get_image_url",
    "get_images_for_style",
    "get_images_for_archetype",
    "get_images_for_usage",
    "get_ai_visible_images",
    "render_image_markdown",
    "reload_images",
]
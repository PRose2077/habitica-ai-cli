"""风格配置加载器

从 YAML 文件加载风格配置，支持动态扩展风格。
只需在 styles/ 目录下添加 YAML 文件即可新增风格。
使用基础模板 + 风格变量的方式生成提示词。
"""

from pathlib import Path
from typing import Optional

import yaml

from habitica_forge.utils.logger import get_logger

logger = get_logger(__name__)

# 风格配置目录
STYLES_DIR = Path(__file__).parent

# 缓存
_style_cache: dict[str, "StyleConfig"] = {}
_all_styles_cache: Optional[list["StyleConfig"]] = None
_case_map_cache: Optional[dict[str, str]] = None
_base_template_cache: Optional[dict] = None


# ============================================
# 模板渲染
# ============================================


def _load_base_template() -> dict:
    """加载基础模板

    Returns:
        基础模板字典
    """
    global _base_template_cache

    if _base_template_cache is not None:
        return _base_template_cache

    template_file = STYLES_DIR / "base_template.yaml"

    if not template_file.exists():
        logger.warning(f"Base template not found: {template_file}")
        return {}

    try:
        with open(template_file, "r", encoding="utf-8") as f:
            _base_template_cache = yaml.safe_load(f) or {}
        return _base_template_cache
    except Exception as e:
        logger.error(f"Failed to load base template: {e}")
        return {}


def _render_template(template: str, variables: dict) -> str:
    """渲染模板

    Args:
        template: 模板字符串，使用 {variable} 作为占位符
        variables: 变量字典

    Returns:
        渲染后的字符串
    """
    try:
        return template.format(**variables)
    except KeyError as e:
        logger.warning(f"Missing variable in template: {e}")
        return template
    except Exception as e:
        logger.error(f"Failed to render template: {e}")
        return template


def _render_prompts(style_data: dict) -> dict:
    """渲染提示词

    将风格变量应用到基础模板，生成最终提示词。

    Args:
        style_data: 风格配置数据（包含变量）

    Returns:
        渲染后的提示词字典
    """
    base_template = _load_base_template()
    variables = style_data.get("variables", {})

    if not base_template:
        # 如果没有基础模板，使用风格配置中的 prompts（向后兼容）
        return style_data.get("prompts", {})

    rendered = {}

    # 渲染 decompose
    if "decompose" in base_template:
        rendered["decompose"] = _render_template(base_template["decompose"], variables)

    # 渲染 title
    if "title" in base_template:
        rendered["title"] = _render_template(base_template["title"], variables)

    # 渲染 corruption
    if "corruption" in base_template:
        rendered["corruption"] = _render_template(base_template["corruption"], variables)

    # 渲染 refine
    if "refine" in base_template:
        refine_template = base_template["refine"]
        if isinstance(refine_template, dict):
            rendered["refine"] = {}
            for field_type, tmpl in refine_template.items():
                rendered["refine"][field_type] = _render_template(tmpl, variables)

    return rendered


# ============================================
# 配置类
# ============================================


class PromptConfig:
    """提示词配置"""

    def __init__(self, data: dict):
        self._data = data

    @property
    def decompose(self) -> str:
        """任务拆解提示词"""
        return self._data.get("decompose", "")

    @property
    def title(self) -> str:
        """称号生成提示词"""
        return self._data.get("title", "")

    @property
    def corruption(self) -> str:
        """任务黑化提示词"""
        return self._data.get("corruption", "")

    def get_refine(self, field_type: str) -> str:
        """获取字段优化提示词

        Args:
            field_type: 字段类型 (title, notes, checklist)
        """
        refine = self._data.get("refine", {})
        if isinstance(refine, dict):
            return refine.get(field_type, refine.get("title", ""))
        return str(refine) if refine else ""


class StyleConfig:
    """风格配置"""

    def __init__(self, data: dict, style_name: str):
        self._data = data
        self._name = style_name
        # 渲染提示词
        self._prompts = PromptConfig(_render_prompts(data))

    @property
    def name(self) -> str:
        """风格名称"""
        return self._name

    @property
    def display_name(self) -> str:
        """显示名称"""
        return self._data.get("display_name", self._name)

    @property
    def description(self) -> str:
        """风格描述"""
        return self._data.get("description", "")

    @property
    def prompts(self) -> PromptConfig:
        """提示词配置"""
        return self._prompts

    @property
    def examples(self) -> dict[str, list[str]]:
        """示例映射"""
        return self._data.get("examples", {})

    @property
    def variables(self) -> dict:
        """风格变量"""
        return self._data.get("variables", {})


# ============================================
# 加载函数
# ============================================


def _load_style_config(style_name: str) -> Optional[StyleConfig]:
    """加载单个风格配置

    Args:
        style_name: 风格名称

    Returns:
        风格配置，如果不存在返回 None
    """
    config_file = STYLES_DIR / f"{style_name}.yaml"

    if not config_file.exists():
        logger.warning(f"Style config not found: {config_file}")
        return None

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            logger.warning(f"Empty style config: {config_file}")
            return None

        return StyleConfig(data, style_name)

    except Exception as e:
        logger.error(f"Failed to load style config {config_file}: {e}")
        return None


def get_style_config(style_name: str) -> StyleConfig:
    """获取风格配置

    优先从缓存读取，缓存未命中则加载配置文件。
    如果配置文件不存在，返回 normal 风格作为回退。

    Args:
        style_name: 风格名称

    Returns:
        风格配置
    """
    # 标准化风格名称
    normalized = style_name.lower()

    # 检查缓存
    if normalized in _style_cache:
        return _style_cache[normalized]

    # 加载配置
    config = _load_style_config(normalized)

    if config is None:
        # 回退到 normal 风格
        if normalized != "normal":
            logger.warning(f"Style '{style_name}' not found, fallback to 'normal'")
            return get_style_config("normal")
        # normal 也不存在，返回空配置
        config = StyleConfig({
            "name": "normal",
            "display_name": "正常风格",
            "description": "默认风格",
            "prompts": {},
        }, "normal")

    _style_cache[normalized] = config
    return config


def get_all_style_configs() -> list[StyleConfig]:
    """获取所有风格配置

    扫描 styles 目录下的所有 YAML 文件（排除 base_template.yaml）。

    Returns:
        风格配置列表
    """
    global _all_styles_cache

    if _all_styles_cache is not None:
        return _all_styles_cache

    configs = []

    for yaml_file in STYLES_DIR.glob("*.yaml"):
        style_name = yaml_file.stem
        # 跳过 base_template
        if style_name == "base_template":
            continue
        config = get_style_config(style_name)
        if config:
            configs.append(config)

    _all_styles_cache = configs
    return configs


def reload_styles() -> None:
    """清除所有风格配置缓存

    用于热重载配置文件。
    """
    global _style_cache, _all_styles_cache, _case_map_cache, _base_template_cache
    _style_cache = {}
    _all_styles_cache = None
    _case_map_cache = None
    _base_template_cache = None
    logger.info("Style cache cleared")


# ============================================
# 动态风格查询函数
# ============================================


def get_all_style_names() -> list[str]:
    """获取所有风格名称列表

    Returns:
        风格名称列表，如 ["normal", "cyberpunk", "wuxia", "fantasy"]
    """
    configs = get_all_style_configs()
    return [c.name for c in configs]


def get_style_display_name(style: str) -> str:
    """获取风格的显示名称

    Args:
        style: 风格名称

    Returns:
        风格的中文显示名称
    """
    config = get_style_config(style)
    return config.display_name


def get_style_description(style: str) -> str:
    """获取风格的描述

    Args:
        style: 风格名称

    Returns:
        风格的描述文字
    """
    config = get_style_config(style)
    return config.description


def get_style_case_map() -> dict[str, str]:
    """获取风格大小写映射表

    动态生成，支持新风格自动加入映射。

    Returns:
        大小写映射字典，如 {"normal": "normal", "Normal": "normal", ...}
    """
    global _case_map_cache

    if _case_map_cache is not None:
        return _case_map_cache

    case_map = {}
    for style_name in get_all_style_names():
        case_map[style_name] = style_name
        case_map[style_name.capitalize()] = style_name
        case_map[style_name.upper()] = style_name

    _case_map_cache = case_map
    return case_map


def normalize_style(style: str) -> str:
    """标准化风格名称

    将任意大小写的风格名称转换为标准小写形式。
    如果风格不存在，返回 "normal" 作为回退。

    Args:
        style: 风格名称（可以是任意大小写）

    Returns:
        标准化的风格名称
    """
    case_map = get_style_case_map()
    return case_map.get(style, "normal")
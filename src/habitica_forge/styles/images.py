"""图片资源加载器

从 images.yaml 加载图片资源配置，提供：
- 按风格获取图片
- 按原型获取图片
- 按用途获取图片
- AI 可见的语义信息
- URL 注入功能
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from habitica_forge.utils.logger import get_logger

logger = get_logger(__name__)

# 图片资源文件路径
IMAGES_FILE = Path(__file__).parent / "images.yaml"

# 缓存
_images_cache: Optional[Dict[str, Any]] = None
_flat_images_cache: Optional[Dict[str, Dict[str, Any]]] = None


# ============================================
# 图片数据类
# ============================================


class ImageResource:
    """图片资源"""

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @property
    def id(self) -> str:
        """图片唯一 ID"""
        return self._data.get("id", "")

    @property
    def title(self) -> str:
        """图片标题（AI 可见）"""
        return self._data.get("title", "")

    @property
    def description(self) -> str:
        """图片描述（AI 可见）"""
        return self._data.get("description", "")

    @property
    def url(self) -> str:
        """图片 URL（仅程序使用）"""
        return self._data.get("url", "")

    @property
    def enabled(self) -> bool:
        """是否启用"""
        return self._data.get("enabled", True)

    @property
    def archetypes(self) -> List[str]:
        """关联的原型列表"""
        return self._data.get("archetypes", [])

    @property
    def usage(self) -> List[str]:
        """用途列表"""
        return self._data.get("usage", [])

    def to_ai_dict(self) -> Dict[str, str]:
        """转换为 AI 可见的字典

        Returns:
            只包含 id, title, description 的字典
        """
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
        }


# ============================================
# 加载函数
# ============================================


def _load_images_config() -> Dict[str, Any]:
    """加载图片资源配置

    Returns:
        配置字典
    """
    global _images_cache

    if _images_cache is not None:
        return _images_cache

    if not IMAGES_FILE.exists():
        logger.warning(f"Images config not found: {IMAGES_FILE}")
        return {}

    try:
        with open(IMAGES_FILE, "r", encoding="utf-8") as f:
            _images_cache = yaml.safe_load(f) or {}
        return _images_cache
    except Exception as e:
        logger.error(f"Failed to load images config: {e}")
        return {}


def _build_flat_cache() -> Dict[str, Dict[str, Any]]:
    """构建扁平化的图片缓存

    将所有风格下的图片合并到一个字典中，方便按 ID 查询。

    Returns:
        图片 ID 到图片数据的映射
    """
    global _flat_images_cache

    if _flat_images_cache is not None:
        return _flat_images_cache

    config = _load_images_config()
    flat: Dict[str, Dict[str, Any]] = {}

    # 处理通用图片
    for img in config.get("common", []):
        if img.get("id"):
            flat[img["id"]] = img

    # 处理各风格图片
    for style in ["fantasy", "cyberpunk", "wuxia", "normal"]:
        for img in config.get(style, []):
            if img.get("id"):
                flat[img["id"]] = img

    _flat_images_cache = flat
    return flat


def reload_images() -> None:
    """清除图片资源缓存"""
    global _images_cache, _flat_images_cache
    _images_cache = None
    _flat_images_cache = None
    logger.info("Images cache cleared")


# ============================================
# 查询函数
# ============================================


def get_image_by_id(image_id: str) -> Optional[ImageResource]:
    """根据 ID 获取图片资源

    Args:
        image_id: 图片 ID

    Returns:
        图片资源，未找到返回 None
    """
    flat = _build_flat_cache()
    data = flat.get(image_id)
    if data:
        return ImageResource(data)
    return None


def get_image_url(image_id: str) -> Optional[str]:
    """根据 ID 获取图片 URL

    Args:
        image_id: 图片 ID

    Returns:
        图片 URL，未找到返回 None
    """
    img = get_image_by_id(image_id)
    if img and img.enabled:
        return img.url
    return None


def get_images_for_style(style: str, enabled_only: bool = True) -> List[ImageResource]:
    """获取指定风格的图片列表

    Args:
        style: 风格名称
        enabled_only: 是否只返回启用的图片

    Returns:
        图片资源列表
    """
    config = _load_images_config()

    # 获取风格图片
    style_images = config.get(style, [])
    # 也包含通用图片
    common_images = config.get("common", [])

    all_images = style_images + common_images

    result = []
    for img_data in all_images:
        img = ImageResource(img_data)
        if not enabled_only or img.enabled:
            result.append(img)

    return result


def get_images_for_archetype(
    archetype: str,
    style: Optional[str] = None,
    enabled_only: bool = True
) -> List[ImageResource]:
    """获取指定原型的图片列表

    Args:
        archetype: 原型名称
        style: 可选的风格过滤
        enabled_only: 是否只返回启用的图片

    Returns:
        图片资源列表
    """
    images = get_images_for_style(style or "common", enabled_only)

    result = []
    for img in images:
        if archetype in img.archetypes:
            result.append(img)

    return result


def get_images_for_usage(
    usage: str,
    style: Optional[str] = None,
    enabled_only: bool = True
) -> List[ImageResource]:
    """获取指定用途的图片列表

    Args:
        usage: 用途名称
        style: 可选的风格过滤
        enabled_only: 是否只返回启用的图片

    Returns:
        图片资源列表
    """
    images = get_images_for_style(style or "common", enabled_only)

    result = []
    for img in images:
        if usage in img.usage:
            result.append(img)

    return result


def get_ai_visible_images(style: Optional[str] = None) -> List[Dict[str, str]]:
    """获取 AI 可见的图片列表

    只返回 id, title, description，不暴露 URL。

    Args:
        style: 可选的风格过滤

    Returns:
        AI 可见的图片字典列表
    """
    if style:
        images = get_images_for_style(style)
    else:
        # 获取所有图片
        flat = _build_flat_cache()
        images = [ImageResource(data) for data in flat.values()]

    return [img.to_ai_dict() for img in images if img.enabled]


# ============================================
# Markdown 生成
# ============================================


def render_image_markdown(
    image_id: str,
    alt_text: Optional[str] = None,
    max_width: Optional[int] = None
) -> str:
    """渲染 Markdown 图片标签

    Args:
        image_id: 图片 ID
        alt_text: 可选的替代文本
        max_width: 可选的最大宽度

    Returns:
        Markdown 图片标签，图片不存在时返回空字符串
    """
    img = get_image_by_id(image_id)

    if not img or not img.enabled:
        return ""

    alt = alt_text or img.title

    if max_width:
        return f'<img src="{img.url}" alt="{alt}" width="{max_width}" />'
    else:
        return f"![{alt}]({img.url})"


# ============================================
# 默认配置
# ============================================


def get_default_max_width() -> int:
    """获取默认最大宽度"""
    config = _load_images_config()
    defaults = config.get("defaults", {})
    return defaults.get("max_width", 200)


def get_default_max_height() -> int:
    """获取默认最大高度"""
    config = _load_images_config()
    defaults = config.get("defaults", {})
    return defaults.get("max_height", 200)
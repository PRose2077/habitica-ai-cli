"""游戏化标签管理模块

使用 Habitica Tags 替代 notes 中的元数据存储，实现：
- 传奇任务标记
- 任务类型标记
- 任务链关联
- 任务原型标记
- 地点标记

Tag 命名规范：
- forge:传奇 - 传奇任务标记
- forge:主线 / forge:远征 / forge:战役 - 传奇类型
- chain:任务链名称 - 任务链关联
- archetype:战斗 / archetype:探索 - 任务原型
- location:城堡 / location:酒馆 - 地点信息
"""

from enum import Enum
from typing import Dict, List, Optional, Set

from habitica_forge.utils.logger import get_logger

logger = get_logger(__name__)


class ForgeTagPrefix(str, Enum):
    """Forge 标签前缀"""

    FORGE = "forge:"  # 传奇任务相关
    CHAIN = "chain:"  # 任务链
    ARCHETYPE = "archetype:"  # 任务原型
    LOCATION = "location:"  # 地点


# 传奇任务类型标签
LEGENDARY_TAG_NAMES = {
    "main": "forge:主线",
    "expedition": "forge:远征",
    "campaign": "forge:战役",
    "escort": "forge:护送",
    "saga": "forge:史诗",
    "chain": "forge:任务链",
}

# 传奇任务标记（无具体类型）
LEGENDARY_TAG = "forge:传奇"

# 任务原型标签映射
ARCHETYPE_TAG_NAMES = {
    "cleanup": "archetype:清理",
    "repair": "archetype:修复",
    "explore": "archetype:探索",
    "craft": "archetype:制作",
    "communicate": "archetype:沟通",
    "learn": "archetype:学习",
    "battle": "archetype:战斗",
    "supply": "archetype:补给",
}


class ForgeTags:
    """Forge 标签集合

    用于收集和管理任务的所有 Forge 相关标签。
    """

    def __init__(self):
        self._tags: Set[str] = set()

    def add_legendary(self, legendary_type: Optional[str] = None) -> "ForgeTags":
        """添加传奇任务标签

        Args:
            legendary_type: 传奇类型 (main/expedition/campaign/escort/saga/chain)
        """
        if legendary_type and legendary_type in LEGENDARY_TAG_NAMES:
            self._tags.add(LEGENDARY_TAG_NAMES[legendary_type])
        else:
            self._tags.add(LEGENDARY_TAG)
        return self

    def add_chain(self, chain_name: str) -> "ForgeTags":
        """添加任务链标签

        Args:
            chain_name: 任务链名称
        """
        if chain_name:
            self._tags.add(f"chain:{chain_name}")
        return self

    def add_archetype(self, archetype: str) -> "ForgeTags":
        """添加任务原型标签

        Args:
            archetype: 任务原型
        """
        if archetype in ARCHETYPE_TAG_NAMES:
            self._tags.add(ARCHETYPE_TAG_NAMES[archetype])
        return self

    def add_location(self, location: str) -> "ForgeTags":
        """添加地点标签

        Args:
            location: 地点名称
        """
        if location:
            self._tags.add(f"location:{location}")
        return self

    def to_list(self) -> List[str]:
        """转换为标签名称列表"""
        return list(self._tags)

    def __bool__(self) -> bool:
        return bool(self._tags)


def parse_forge_tags(tag_names: List[str]) -> Dict[str, Optional[str]]:
    """从标签名称列表解析 Forge 相关信息

    Args:
        tag_names: 标签名称列表

    Returns:
        解析出的信息字典：
        {
            "is_legendary": bool,
            "legendary_type": Optional[str],
            "chain_name": Optional[str],
            "archetype": Optional[str],
            "location": Optional[str],
        }
    """
    result = {
        "is_legendary": False,
        "legendary_type": None,
        "chain_name": None,
        "archetype": None,
        "location": None,
    }

    for tag_name in tag_names:
        # 检查传奇任务标记
        if tag_name == LEGENDARY_TAG:
            result["is_legendary"] = True
        elif tag_name in LEGENDARY_TAG_NAMES.values():
            result["is_legendary"] = True
            # 反向查找类型
            for ltype, lname in LEGENDARY_TAG_NAMES.items():
                if tag_name == lname:
                    result["legendary_type"] = ltype
                    break

        # 检查任务链
        elif tag_name.startswith("chain:"):
            result["chain_name"] = tag_name[6:]  # 去掉 "chain:"

        # 检查任务原型
        elif tag_name.startswith("archetype:"):
            result["archetype"] = tag_name[10:]  # 去掉 "archetype:"

        # 检查地点
        elif tag_name.startswith("location:"):
            result["location"] = tag_name[9:]  # 去掉 "location:"

    return result


async def ensure_tags_exist(
    client,
    tag_names: List[str],
    existing_tags: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """确保指定的标签存在，返回标签名称到 ID 的映射

    Args:
        client: HabiticaClient 实例
        tag_names: 需要的标签名称列表
        existing_tags: 现有的标签映射 {name: id}，如果为 None 则自动获取

    Returns:
        标签名称到 ID 的映射字典
    """
    if existing_tags is None:
        tags = await client.get_tags()
        existing_tags = {tag.name: tag.id for tag in tags}

    result = {}
    for name in tag_names:
        if name in existing_tags:
            result[name] = existing_tags[name]
        else:
            # 创建新标签
            new_tag = await client.create_tag(name)
            result[name] = new_tag.id
            existing_tags[name] = new_tag.id
            logger.debug(f"Created new tag: {name}")

    return result


def get_tag_ids_for_forge_tags(
    forge_tag_names: List[str],
    tag_name_to_id: Dict[str, str],
) -> List[str]:
    """获取 Forge 标签对应的 ID 列表

    Args:
        forge_tag_names: Forge 标签名称列表
        tag_name_to_id: 标签名称到 ID 的映射

    Returns:
        标签 ID 列表
    """
    ids = []
    for name in forge_tag_names:
        if name in tag_name_to_id:
            ids.append(tag_name_to_id[name])
    return ids


def build_forge_tags_from_result(result) -> ForgeTags:
    """从 SmartDecomposeResult 构建 Forge 标签

    Args:
        result: SmartDecomposeResult 对象

    Returns:
        ForgeTags 实例
    """
    tags = ForgeTags()

    if getattr(result, "is_legendary", False):
        tags.add_legendary(getattr(result, "legendary_type", None))

    if getattr(result, "chain_name", None):
        tags.add_chain(result.chain_name)

    if getattr(result, "archetype", None):
        tags.add_archetype(result.archetype)

    if getattr(result, "location", None):
        tags.add_location(result.location)

    return tags
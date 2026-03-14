"""本地缓存引擎"""

import json
import time
from pathlib import Path
from typing import Any, Dict, Generic, List, Optional, TypeVar

from habitica_forge.utils.logger import get_logger

logger = get_logger(__name__)

# 缓存目录
CACHE_DIR = Path.home() / ".config" / "habitica-forge" / "cache"

# 默认 TTL（秒）
DEFAULT_TTL = 300  # 5 分钟

T = TypeVar("T")


class CacheEntry(Generic[T]):
    """缓存条目"""

    def __init__(
        self,
        data: T,
        timestamp: Optional[float] = None,
        ttl: int = DEFAULT_TTL,
    ):
        """
        初始化缓存条目

        Args:
            data: 缓存数据
            timestamp: 创建时间戳，默认为当前时间
            ttl: 过期时间（秒）
        """
        self.data = data
        self.timestamp = timestamp or time.time()
        self.ttl = ttl

    def is_expired(self) -> bool:
        """检查是否过期"""
        return time.time() - self.timestamp > self.ttl

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        return {
            "data": self.data,
            "timestamp": self.timestamp,
            "ttl": self.ttl,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        """从字典反序列化"""
        return cls(
            data=data["data"],
            timestamp=data["timestamp"],
            ttl=data["ttl"],
        )


class Cache:
    """本地文件缓存"""

    def __init__(self, cache_dir: Optional[Path] = None, default_ttl: int = DEFAULT_TTL):
        """
        初始化缓存

        Args:
            cache_dir: 缓存目录，默认为 ~/.config/habitica-forge/cache/
            default_ttl: 默认过期时间（秒）
        """
        self.cache_dir = cache_dir or CACHE_DIR
        self.default_ttl = default_ttl
        self._ensure_cache_dir()

    def _ensure_cache_dir(self) -> None:
        """确保缓存目录存在"""
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        return self.cache_dir / f"{key}.json"

    def get(
        self,
        key: str,
        default: Optional[T] = None,
    ) -> Optional[T]:
        """
        获取缓存数据

        Args:
            key: 缓存键
            default: 默认值

        Returns:
            缓存数据，如果不存在或过期则返回 default
        """
        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            logger.debug(f"Cache miss: {key}")
            return default

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                entry_data = json.load(f)

            entry = CacheEntry.from_dict(entry_data)

            if entry.is_expired():
                logger.debug(f"Cache expired: {key}")
                self.delete(key)
                return default

            logger.debug(f"Cache hit: {key}")
            return entry.data

        except (json.JSONDecodeError, KeyError, IOError) as e:
            logger.warning(f"Failed to read cache {key}: {e}")
            self.delete(key)
            return default

    def set(
        self,
        key: str,
        data: T,
        ttl: Optional[int] = None,
    ) -> None:
        """
        设置缓存数据

        Args:
            key: 缓存键
            data: 缓存数据
            ttl: 过期时间（秒），默认使用 default_ttl
        """
        cache_path = self._get_cache_path(key)
        entry = CacheEntry(data=data, ttl=ttl or self.default_ttl)

        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(entry.to_dict(), f, ensure_ascii=False, indent=2)
            logger.debug(f"Cache set: {key}")
        except IOError as e:
            logger.error(f"Failed to write cache {key}: {e}")

    def delete(self, key: str) -> bool:
        """
        删除缓存

        Args:
            key: 缓存键

        Returns:
            是否成功删除
        """
        cache_path = self._get_cache_path(key)

        if cache_path.exists():
            try:
                cache_path.unlink()
                logger.debug(f"Cache deleted: {key}")
                return True
            except IOError as e:
                logger.error(f"Failed to delete cache {key}: {e}")
                return False
        return False

    def clear(self) -> None:
        """清空所有缓存"""
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except IOError as e:
                logger.warning(f"Failed to delete {cache_file}: {e}")
        logger.info("Cache cleared")


class TaskCache:
    """任务缓存管理器"""

    CACHE_KEY = "tasks"

    def __init__(self, cache: Optional[Cache] = None, ttl: int = DEFAULT_TTL):
        """
        初始化任务缓存

        Args:
            cache: Cache 实例
            ttl: 过期时间（秒）
        """
        self.cache = cache or Cache()
        self.ttl = ttl

    def get_tasks(self) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的任务列表"""
        return self.cache.get(self.CACHE_KEY)

    def set_tasks(self, tasks: List[Dict[str, Any]]) -> None:
        """设置任务缓存"""
        self.cache.set(self.CACHE_KEY, tasks, ttl=self.ttl)

    def invalidate(self) -> None:
        """清除任务缓存"""
        self.cache.delete(self.CACHE_KEY)
        logger.info("Task cache invalidated")


class TagCache:
    """标签缓存管理器"""

    CACHE_KEY = "tags"

    def __init__(self, cache: Optional[Cache] = None, ttl: int = DEFAULT_TTL):
        """
        初始化标签缓存

        Args:
            cache: Cache 实例
            ttl: 过期时间（秒）
        """
        self.cache = cache or Cache()
        self.ttl = ttl

    def get_tags(self) -> Optional[List[Dict[str, Any]]]:
        """获取缓存的标签列表"""
        return self.cache.get(self.CACHE_KEY)

    def set_tags(self, tags: List[Dict[str, Any]]) -> None:
        """设置标签缓存"""
        self.cache.set(self.CACHE_KEY, tags, ttl=self.ttl)

    def invalidate(self) -> None:
        """清除标签缓存"""
        self.cache.delete(self.CACHE_KEY)
        logger.info("Tag cache invalidated")


class IndexCache:
    """任务编号映射缓存 - 将用户友好的编号映射到完整 UUID"""

    CACHE_KEY = "task_index"
    CHECKLIST_KEY = "checklist_index"
    TITLE_INDEX_KEY = "title_index"

    def __init__(self, cache: Optional[Cache] = None, ttl: int = DEFAULT_TTL):
        """
        初始化编号缓存

        Args:
            cache: Cache 实例
            ttl: 过期时间（秒）
        """
        self.cache = cache or Cache()
        self.ttl = ttl

    def get_mapping(self) -> Optional[Dict[str, str]]:
        """获取编号到 UUID 的映射 {编号: UUID}"""
        return self.cache.get(self.CACHE_KEY)

    def set_mapping(self, mapping: Dict[str, str]) -> None:
        """设置编号映射"""
        self.cache.set(self.CACHE_KEY, mapping, ttl=self.ttl)

    def get_uuid(self, index: str) -> Optional[str]:
        """根据编号获取 UUID"""
        mapping = self.get_mapping()
        if mapping:
            return mapping.get(index)
        return None

    def get_checklist_mapping(self, task_id: str) -> Optional[Dict[str, str]]:
        """获取子任务编号到 ID 的映射"""
        key = f"{self.CHECKLIST_KEY}_{task_id}"
        return self.cache.get(key)

    def set_checklist_mapping(self, task_id: str, mapping: Dict[str, str]) -> None:
        """设置子任务编号映射"""
        key = f"{self.CHECKLIST_KEY}_{task_id}"
        self.cache.set(key, mapping, ttl=self.ttl)

    def get_checklist_item_id(self, task_id: str, index: str) -> Optional[str]:
        """根据任务ID和子任务编号获取子任务ID"""
        mapping = self.get_checklist_mapping(task_id)
        if mapping:
            return mapping.get(index)
        return None

    # ============================================
    # 称号编号映射
    # ============================================

    def get_title_mapping(self) -> Optional[Dict[str, Dict[str, str]]]:
        """
        获取称号编号到称号信息的映射

        Returns:
            {编号: {"id": tag_id, "title": 称号名, "status": 状态}}
        """
        return self.cache.get(self.TITLE_INDEX_KEY)

    def set_title_mapping(self, mapping: Dict[str, Dict[str, str]]) -> None:
        """设置称号编号映射"""
        self.cache.set(self.TITLE_INDEX_KEY, mapping, ttl=self.ttl)

    def get_title_info(self, index: str) -> Optional[Dict[str, str]]:
        """
        根据编号获取称号信息

        Args:
            index: 称号编号

        Returns:
            {"id": tag_id, "title": 称号名, "status": 状态} 或 None
        """
        mapping = self.get_title_mapping()
        if mapping:
            return mapping.get(index)
        return None

    def invalidate(self) -> None:
        """清除编号缓存"""
        self.cache.delete(self.CACHE_KEY)
        self.cache.delete(self.TITLE_INDEX_KEY)
        logger.info("Index cache invalidated")


class CacheManager:
    """缓存管理器 - 统一管理所有缓存"""

    def __init__(self, default_ttl: int = DEFAULT_TTL):
        """
        初始化缓存管理器

        Args:
            default_ttl: 默认过期时间（秒）
        """
        self.cache = Cache(default_ttl=default_ttl)
        self.tasks = TaskCache(self.cache, ttl=default_ttl)
        self.tags = TagCache(self.cache, ttl=default_ttl)
        self.index = IndexCache(self.cache, ttl=default_ttl)

    def invalidate_all(self) -> None:
        """清除所有缓存"""
        self.tasks.invalidate()
        self.tags.invalidate()
        self.index.invalidate()
        logger.info("All caches invalidated")

    def clear_all(self) -> None:
        """清空所有缓存文件"""
        self.cache.clear()


# 全局缓存管理器实例（延迟初始化）
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
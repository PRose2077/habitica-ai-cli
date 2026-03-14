"""缓存引擎单元测试"""

import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from habitica_forge.core.cache import (
    CACHE_DIR,
    Cache,
    CacheEntry,
    CacheManager,
    TagCache,
    TaskCache,
    get_cache_manager,
)


class TestCacheEntry:
    """CacheEntry 测试"""

    def test_init(self):
        """测试初始化"""
        entry = CacheEntry(data={"key": "value"}, ttl=60)
        assert entry.data == {"key": "value"}
        assert entry.ttl == 60
        assert entry.timestamp is not None

    def test_is_expired_false(self):
        """测试未过期"""
        entry = CacheEntry(data="test", ttl=300)
        assert entry.is_expired() is False

    def test_is_expired_true(self):
        """测试已过期"""
        entry = CacheEntry(data="test", ttl=1, timestamp=time.time() - 10)
        assert entry.is_expired() is True

    def test_to_dict(self):
        """测试序列化"""
        entry = CacheEntry(data="test", ttl=60, timestamp=1000.0)
        result = entry.to_dict()
        assert result["data"] == "test"
        assert result["ttl"] == 60
        assert result["timestamp"] == 1000.0

    def test_from_dict(self):
        """测试反序列化"""
        data = {"data": "test", "ttl": 60, "timestamp": 1000.0}
        entry = CacheEntry.from_dict(data)
        assert entry.data == "test"
        assert entry.ttl == 60
        assert entry.timestamp == 1000.0


class TestCache:
    """Cache 测试"""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path: Path):
        """创建临时缓存目录"""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        return cache_dir

    @pytest.fixture
    def cache(self, temp_cache_dir: Path):
        """创建 Cache 实例"""
        return Cache(cache_dir=temp_cache_dir, default_ttl=60)

    def test_ensure_cache_dir(self, tmp_path: Path):
        """测试缓存目录创建"""
        cache_dir = tmp_path / "new_cache"
        assert not cache_dir.exists()
        Cache(cache_dir=cache_dir)
        assert cache_dir.exists()

    def test_set_and_get(self, cache: Cache):
        """测试设置和获取缓存"""
        cache.set("test_key", {"name": "test"})
        result = cache.get("test_key")
        assert result == {"name": "test"}

    def test_get_missing_key(self, cache: Cache):
        """测试获取不存在的缓存"""
        result = cache.get("missing_key", default="default")
        assert result == "default"

    def test_get_expired(self, cache: Cache):
        """测试获取过期缓存"""
        # 设置一个已经过期的缓存
        entry = CacheEntry(data="expired", ttl=1, timestamp=time.time() - 10)
        cache_path = cache._get_cache_path("expired_key")
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(entry.to_dict(), f)

        result = cache.get("expired_key", default=None)
        assert result is None
        # 过期缓存应该被删除
        assert not cache_path.exists()

    def test_delete(self, cache: Cache):
        """测试删除缓存"""
        cache.set("delete_key", "value")
        assert cache.get("delete_key") == "value"

        success = cache.delete("delete_key")
        assert success is True
        assert cache.get("delete_key") is None

    def test_delete_nonexistent(self, cache: Cache):
        """测试删除不存在的缓存"""
        success = cache.delete("nonexistent_key")
        assert success is False

    def test_clear(self, cache: Cache):
        """测试清空缓存"""
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None
        assert cache.get("key3") is None

    def test_custom_ttl(self, cache: Cache):
        """测试自定义 TTL"""
        cache.set("custom_ttl_key", "value", ttl=3600)

        result = cache.get("custom_ttl_key")
        assert result == "value"

        # 验证 TTL 被正确保存
        cache_path = cache._get_cache_path("custom_ttl_key")
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["ttl"] == 3600


class TestTaskCache:
    """TaskCache 测试"""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path: Path):
        """创建临时缓存目录"""
        return tmp_path / "cache"

    @pytest.fixture
    def task_cache(self, temp_cache_dir: Path):
        """创建 TaskCache 实例"""
        cache = Cache(cache_dir=temp_cache_dir)
        return TaskCache(cache=cache)

    def test_get_tasks(self, task_cache: TaskCache):
        """测试获取任务缓存"""
        tasks = [
            {"id": "task-1", "text": "Task 1"},
            {"id": "task-2", "text": "Task 2"},
        ]
        task_cache.set_tasks(tasks)
        result = task_cache.get_tasks()
        assert result == tasks

    def test_get_tasks_empty(self, task_cache: TaskCache):
        """测试获取空任务缓存"""
        result = task_cache.get_tasks()
        assert result is None

    def test_invalidate(self, task_cache: TaskCache):
        """测试清除任务缓存"""
        task_cache.set_tasks([{"id": "task-1"}])
        assert task_cache.get_tasks() is not None

        task_cache.invalidate()
        assert task_cache.get_tasks() is None


class TestTagCache:
    """TagCache 测试"""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path: Path):
        """创建临时缓存目录"""
        return tmp_path / "cache"

    @pytest.fixture
    def tag_cache(self, temp_cache_dir: Path):
        """创建 TagCache 实例"""
        cache = Cache(cache_dir=temp_cache_dir)
        return TagCache(cache=cache)

    def test_get_tags(self, tag_cache: TagCache):
        """测试获取标签缓存"""
        tags = [
            {"id": "tag-1", "name": "Work"},
            {"id": "tag-2", "name": "Personal"},
        ]
        tag_cache.set_tags(tags)
        result = tag_cache.get_tags()
        assert result == tags

    def test_invalidate(self, tag_cache: TagCache):
        """测试清除标签缓存"""
        tag_cache.set_tags([{"id": "tag-1"}])
        assert tag_cache.get_tags() is not None

        tag_cache.invalidate()
        assert tag_cache.get_tags() is None


class TestCacheManager:
    """CacheManager 测试"""

    @pytest.fixture
    def temp_cache_dir(self, tmp_path: Path):
        """创建临时缓存目录"""
        return tmp_path / "cache"

    @pytest.fixture
    def cache_manager(self, temp_cache_dir: Path):
        """创建 CacheManager 实例"""
        with patch("habitica_forge.core.cache.CACHE_DIR", temp_cache_dir):
            return CacheManager(default_ttl=60)

    def test_init(self, cache_manager: CacheManager):
        """测试初始化"""
        assert cache_manager.tasks is not None
        assert cache_manager.tags is not None

    def test_invalidate_all(self, cache_manager: CacheManager):
        """测试清除所有缓存"""
        cache_manager.tasks.set_tasks([{"id": "task-1"}])
        cache_manager.tags.set_tags([{"id": "tag-1"}])

        cache_manager.invalidate_all()

        assert cache_manager.tasks.get_tasks() is None
        assert cache_manager.tags.get_tags() is None

    def test_clear_all(self, cache_manager: CacheManager, temp_cache_dir: Path):
        """测试清空所有缓存文件"""
        cache_manager.tasks.set_tasks([{"id": "task-1"}])
        cache_manager.tags.set_tags([{"id": "tag-1"}])

        cache_manager.clear_all()

        # 验证缓存目录中没有 json 文件
        json_files = list(temp_cache_dir.glob("*.json"))
        assert len(json_files) == 0


class TestGetCacheManager:
    """get_cache_manager 测试"""

    def test_singleton(self):
        """测试单例"""
        # 重置全局实例
        import habitica_forge.core.cache as cache_module

        cache_module._cache_manager = None

        manager1 = get_cache_manager()
        manager2 = get_cache_manager()

        assert manager1 is manager2


class TestDefaultCacheDir:
    """默认缓存目录测试"""

    def test_cache_dir_exists(self):
        """测试默认缓存目录常量"""
        expected_dir = Path.home() / ".config" / "habitica-forge" / "cache"
        assert CACHE_DIR == expected_dir
"""Habitica 异步 HTTP 客户端"""

import asyncio
import random
from typing import Any, Dict, List, Literal, Optional, Union

import httpx

from habitica_forge.core.config import settings
from habitica_forge.models import ChecklistItem, HabiticaAPIResponse, TagData, TaskData
from habitica_forge.utils.logger import get_logger

logger = get_logger(__name__)

# API 基础 URL
HABITICA_API_BASE = "https://habitica.com/api/v3"

# 任务类型过滤参数
TaskTypeFilter = Literal[
    "habits",
    "dailys",
    "todos",
    "rewards",
    "completedTodos",
]


class RetryError(Exception):
    """重试次数耗尽错误"""

    pass


class HabiticaClient:
    """Habitica 异步客户端"""

    def __init__(
        self,
        max_retries: int = 3,
        base_backoff: float = 1.0,
        max_backoff: float = 60.0,
        timeout: float = 30.0,
    ):
        """
        初始化客户端

        Args:
            max_retries: 最大重试次数
            base_backoff: 基础退避时间（秒）
            max_backoff: 最大退避时间（秒）
            timeout: 请求超时时间（秒）
        """
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "x-api-user": settings.habitica_user_id,
            "x-api-key": settings.habitica_api_token,
            "x-client": f"{settings.habitica_user_id}-habitica-forge",
            "Content-Type": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            # 禁用 httpx 的日志输出
            import logging
            logging.getLogger("httpx").setLevel(logging.WARNING)
            logging.getLogger("httpcore").setLevel(logging.WARNING)

            self._client = httpx.AsyncClient(
                base_url=HABITICA_API_BASE,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "HabiticaClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def _calculate_backoff(self, attempt: int) -> float:
        """计算指数退避时间"""
        backoff = self.base_backoff * (2**attempt) + random.uniform(0, 1)
        return min(backoff, self.max_backoff)

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        带重试机制的请求

        Args:
            method: HTTP 方法
            url: 请求 URL
            **kwargs: 传递给 httpx 的其他参数

        Returns:
            API 响应数据

        Raises:
            RetryError: 重试次数耗尽
            httpx.HTTPStatusError: HTTP 错误
        """
        client = await self._get_client()
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await client.request(method, url, **kwargs)

                # 检查 429 Too Many Requests
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", "1"))
                    backoff = min(retry_after, self.max_backoff)
                    logger.warning(
                        f"Rate limited (429), waiting {backoff:.1f}s before retry"
                    )
                    await asyncio.sleep(backoff)
                    continue

                # 检查 5xx 错误
                if response.status_code >= 500:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Server error ({response.status_code}), "
                        f"retrying in {backoff:.1f}s (attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(backoff)
                    continue

                # 检查其他错误
                response.raise_for_status()

                return response.json()

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code < 500 and e.response.status_code != 429:
                    # 非服务器错误，不重试
                    raise

                if attempt < self.max_retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(
                        f"HTTP error, retrying in {backoff:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(backoff)
                else:
                    raise RetryError(f"Max retries ({self.max_retries}) exceeded") from e

            except httpx.RequestError as e:
                last_error = e
                if attempt < self.max_retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Request error: {e}, retrying in {backoff:.1f}s "
                        f"(attempt {attempt + 1}/{self.max_retries})"
                    )
                    await asyncio.sleep(backoff)
                else:
                    raise RetryError(f"Max retries ({self.max_retries}) exceeded") from e

        raise RetryError(f"Max retries ({self.max_retries}) exceeded") from last_error

    # ============================================
    # Tasks API
    # ============================================

    async def get_tasks(
        self,
        task_type: Optional[TaskTypeFilter] = None,
    ) -> List[TaskData]:
        """
        获取用户的所有任务

        Args:
            task_type: 任务类型过滤 (habits, dailys, todos, rewards, completedTodos)

        Returns:
            任务列表
        """
        params = {}
        if task_type:
            params["type"] = task_type

        response = await self._request_with_retry("GET", "/tasks/user", params=params)

        tasks = []
        for item in response.get("data", []):
            try:
                tasks.append(TaskData.from_api_response(item))
            except Exception as e:
                logger.warning(f"Failed to parse task: {e}")
                continue

        logger.debug(f"Fetched {len(tasks)} tasks (type={task_type})")
        return tasks

    async def get_task(self, task_id: str) -> TaskData:
        """
        获取单个任务

        Args:
            task_id: 任务 ID 或 alias

        Returns:
            任务数据
        """
        response = await self._request_with_retry("GET", f"/tasks/{task_id}")
        return TaskData.from_api_response(response.get("data", {}))

    async def create_task(self, task: TaskData) -> TaskData:
        """
        创建新任务

        Args:
            task: 任务数据

        Returns:
            创建的任务数据（包含 id）
        """
        response = await self._request_with_retry(
            "POST",
            "/tasks/user",
            json=task.to_dict(),
        )
        created = TaskData.from_api_response(response.get("data", {}))
        logger.info(f"Created task: {created.id} - {created.text}")
        return created

    async def update_task(
        self,
        task_id: str,
        **updates,
    ) -> TaskData:
        """
        更新任务

        Args:
            task_id: 任务 ID
            **updates: 要更新的字段

        Returns:
            更新后的任务数据
        """
        response = await self._request_with_retry(
            "PUT",
            f"/tasks/{task_id}",
            json=updates,
        )
        updated = TaskData.from_api_response(response.get("data", {}))
        logger.info(f"Updated task: {task_id}")
        return updated

    async def complete_task(self, task_id: str) -> Dict[str, Any]:
        """
        完成任务

        Args:
            task_id: 任务 ID

        Returns:
            API 响应数据
        """
        response = await self._request_with_retry(
            "POST",
            f"/tasks/{task_id}/score/up",
        )
        logger.info(f"Completed task: {task_id}")
        return response

    async def delete_task(self, task_id: str) -> bool:
        """
        删除任务

        Args:
            task_id: 任务 ID

        Returns:
            是否成功
        """
        await self._request_with_retry("DELETE", f"/tasks/{task_id}")
        logger.info(f"Deleted task: {task_id}")
        return True

    # ============================================
    # Checklist API
    # ============================================

    async def add_checklist_item(
        self,
        task_id: str,
        text: str,
        completed: bool = False,
    ) -> ChecklistItem:
        """
        添加 Checklist 项

        Args:
            task_id: 任务 ID
            text: Checklist 文本
            completed: 是否已完成

        Returns:
            创建的 Checklist 项
        """
        response = await self._request_with_retry(
            "POST",
            f"/tasks/{task_id}/checklist",
            json={"text": text, "completed": completed},
        )
        data = response.get("data", {})
        item = ChecklistItem(
            id=data.get("id"),
            text=data.get("text", text),
            completed=data.get("completed", completed),
        )
        logger.info(f"Added checklist item to task {task_id}: {text}")
        return item

    async def update_checklist_item(
        self,
        task_id: str,
        item_id: str,
        text: Optional[str] = None,
        completed: Optional[bool] = None,
    ) -> ChecklistItem:
        """
        更新 Checklist 项

        Args:
            task_id: 任务 ID
            item_id: Checklist 项 ID
            text: 新文本
            completed: 完成状态

        Returns:
            更新后的 Checklist 项
        """
        data = {}
        if text is not None:
            data["text"] = text
        if completed is not None:
            data["completed"] = completed

        response = await self._request_with_retry(
            "PUT",
            f"/tasks/{task_id}/checklist/{item_id}",
            json=data,
        )
        result = response.get("data", {})
        item = ChecklistItem(
            id=result.get("id", item_id),
            text=result.get("text", text or ""),
            completed=result.get("completed", completed or False),
        )
        logger.info(f"Updated checklist item {item_id} in task {task_id}")
        return item

    async def complete_checklist_item(
        self,
        task_id: str,
        item_id: str,
    ) -> ChecklistItem:
        """
        完成 Checklist 项（打勾）

        Args:
            task_id: 任务 ID
            item_id: Checklist 项 ID

        Returns:
            更新后的 Checklist 项
        """
        return await self.update_checklist_item(task_id, item_id, completed=True)

    async def delete_checklist_item(
        self,
        task_id: str,
        item_id: str,
    ) -> bool:
        """
        删除 Checklist 项

        Args:
            task_id: 任务 ID
            item_id: Checklist 项 ID

        Returns:
            是否成功
        """
        await self._request_with_retry(
            "DELETE",
            f"/tasks/{task_id}/checklist/{item_id}",
        )
        logger.info(f"Deleted checklist item {item_id} from task {task_id}")
        return True

    # ============================================
    # Tags API
    # ============================================

    async def get_tags(self) -> List[TagData]:
        """
        获取所有标签

        Returns:
            标签列表
        """
        response = await self._request_with_retry("GET", "/tags")
        tags = [TagData.from_api_response(item) for item in response.get("data", [])]
        logger.debug(f"Fetched {len(tags)} tags")
        return tags

    async def create_tag(self, name: str) -> TagData:
        """
        创建新标签

        Args:
            name: 标签名称

        Returns:
            创建的标签数据
        """
        response = await self._request_with_retry(
            "POST",
            "/tags",
            json={"name": name},
        )
        tag = TagData.from_api_response(response.get("data", {}))
        logger.info(f"Created tag: {tag.id} - {tag.name}")
        return tag

    async def update_tag(self, tag_id: str, name: str) -> TagData:
        """
        更新标签名称

        Args:
            tag_id: 标签 ID
            name: 新名称

        Returns:
            更新后的标签数据
        """
        response = await self._request_with_retry(
            "PUT",
            f"/tags/{tag_id}",
            json={"name": name},
        )
        tag = TagData.from_api_response(response.get("data", {}))
        logger.info(f"Updated tag {tag_id} to: {name}")
        return tag

    async def delete_tag(self, tag_id: str) -> bool:
        """
        删除标签

        Args:
            tag_id: 标签 ID

        Returns:
            是否成功
        """
        await self._request_with_retry("DELETE", f"/tags/{tag_id}")
        logger.info(f"Deleted tag: {tag_id}")
        return True

    async def add_tag_to_task(self, task_id: str, tag_id: str) -> bool:
        """
        为任务添加标签

        Args:
            task_id: 任务 ID
            tag_id: 标签 ID

        Returns:
            是否成功
        """
        await self._request_with_retry(
            "POST",
            f"/tasks/{task_id}/tags/{tag_id}",
        )
        logger.info(f"Added tag {tag_id} to task {task_id}")
        return True

    async def remove_tag_from_task(self, task_id: str, tag_id: str) -> bool:
        """
        从任务移除标签

        Args:
            task_id: 任务 ID
            tag_id: 标签 ID

        Returns:
            是否成功
        """
        await self._request_with_retry(
            "DELETE",
            f"/tasks/{task_id}/tags/{tag_id}",
        )
        logger.info(f"Removed tag {tag_id} from task {task_id}")
        return True

    async def get_or_create_tag(self, name: str) -> TagData:
        """
        获取或创建标签

        Args:
            name: 标签名称

        Returns:
            标签数据
        """
        tags = await self.get_tags()
        for tag in tags:
            if tag.name == name:
                return tag
        return await self.create_tag(name)


# 全局客户端实例（延迟初始化）
_client_instance: Optional[HabiticaClient] = None


def get_client() -> HabiticaClient:
    """获取全局客户端实例"""
    global _client_instance
    if _client_instance is None:
        _client_instance = HabiticaClient()
    return _client_instance
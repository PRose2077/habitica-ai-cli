from typing import Any, Dict, List, Optional, Union
import requests
from pydantic import TypeAdapter

from src.model.client import HabiticaClient
from src.model.models import Task, TaskType


class TaskService:
    """任务相关服务。

    封装所有与 Habitica 任务相关的操作，包括获取任务、创建任务、完成任务等。
    """

    def __init__(self, client: HabiticaClient):
        """初始化任务服务。

        Args:
            client: HabiticaClient 实例，用于 API 连接。
        """
        self._client = client

    def fetch_tasks(self, task_type: Optional[TaskType] = None) -> List[Task]:
        """获取用户的任务列表。

        Args:
            task_type: 可选的任务类型过滤（habit/daily/todo/reward）。

        Returns:
            任务对象列表。
        """
        url = f"{self._client.BASE_URL}/tasks/user"
        params = {"type": task_type.value} if task_type else {}
        resp = requests.get(url, headers=self._client.headers, params=params)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        adapter = TypeAdapter(List[Task])
        return adapter.validate_python(data)

    def create_task(
        self,
        *,
        text: str,
        task_type: Union[TaskType, str],
        notes: str = "",
        priority: float = 1.0,
        date: Optional[str] = None,
        checklist: Optional[List[Dict[str, Any]]] = None,
    ) -> dict:
        """创建新任务。"""
        return self._client.create_task(
            text=text,
            task_type=task_type,
            notes=notes,
            priority=priority,
            date=date,
            checklist=checklist,
        )

    def score_task(self, task_id: str, direction: str = "up") -> dict:
        """完成任务（正向或负向）。

        Args:
            task_id: 任务 ID。
            direction: 方向，"up" 表示正向（+），"down" 表示负向（-）。

        Returns:
            API 响应数据。
        """
        url = f"{self._client.BASE_URL}/tasks/{task_id}/score/{direction}"
        resp = requests.post(url, headers=self._client.headers)
        resp.raise_for_status()
        return resp.json()
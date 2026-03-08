import os
from typing import Any, Dict, Optional, Union

import requests

from src.model.models import TaskType

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional; silently continue if not installed
    pass


class HabiticaClient:
    """Habitica API 连接客户端。

    仅负责建立与 Habitica API 的连接和基础 HTTP 请求。
    """

    BASE_URL = "https://habitica.com/api/v3"

    def __init__(self):
        """从环境变量读取 HABITICA_USER_ID 和 HABITICA_API_TOKEN。

        支持通过安装 python-dotenv 并在仓库根目录放置 `.env` 文件来加载。
        必须设置环境变量 `HABITICA_USER_ID` 和 `HABITICA_API_TOKEN`。
        """
        user_id = os.getenv("HABITICA_USER_ID")
        api_token = os.getenv("HABITICA_API_TOKEN")

        if not user_id or not api_token:
            raise ValueError("Environment variables HABITICA_USER_ID and HABITICA_API_TOKEN must be set")

        self.headers: Dict[str, str] = {
            "x-api-user": user_id,
            "x-api-key": api_token,
            "x-client": f"{user_id}-habitica-ai",
            "Content-Type": "application/json",
        }

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """发送基础 HTTP 请求并返回 JSON 响应。"""
        url = f"{self.BASE_URL}{path}"
        response = requests.request(method, url, headers=self.headers, params=params, json=json)
        response.raise_for_status()
        return response.json()

    def create_task(
        self,
        *,
        text: str,
        task_type: Union[TaskType, str],
        notes: str = "",
        priority: float = 1.0,
        date: Optional[str] = None,
        checklist: Optional[list[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """创建 Habitica 任务。"""
        type_value = task_type.value if isinstance(task_type, TaskType) else task_type
        payload: Dict[str, Any] = {
            "type": type_value,
            "text": text,
            "notes": notes,
            "priority": priority,
        }

        if date:
            payload["date"] = date
        if checklist:
            payload["checklist"] = checklist

        return self.request("POST", "/tasks/user", json=payload)


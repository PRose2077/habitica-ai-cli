from typing import List, Optional
import requests

from src.model.models import Task, TaskType


class HabiticaClient:
    BASE_URL = "https://habitica.com/api/v3"

    def __init__(self, user_id: str, api_token: str):
        self.headers = {
            "x-api-user": user_id,
            "x-api-key": api_token,
            "Content-Type": "application/json",
        }

    def fetch_tasks(self, task_type: Optional[TaskType] = None) -> List[Task]:
        url = f"{self.BASE_URL}/tasks/user"
        params = {"type": task_type.value} if task_type else {}
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return [Task.from_dict(item) for item in data]

    def score_task(self, task_id: str, direction: str = "up") -> dict:
        url = f"{self.BASE_URL}/tasks/{task_id}/score/{direction}"
        resp = requests.post(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json()

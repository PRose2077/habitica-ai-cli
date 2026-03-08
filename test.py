import sys
from pathlib import Path
import os

# 确保能导入 src 下的包（运行 test.py 时将 src 加入 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from model.client import HabiticaClient
from model.models import TaskType


def run_create_task_test() -> None:
    """连接 Habitica 并创建一个 TODO 任务。"""
    try:
        client = HabiticaClient()
    except ValueError as exc:
        print(f"环境变量缺失: {exc}")
        return

    text = os.getenv("HABITICA_TEST_TASK_TEXT", "[AI Test] 连接 Habitica 创建任务")
    notes = os.getenv("HABITICA_TEST_TASK_NOTES", "由 test.py 自动创建")

    created = client.create_task(
        text=text,
        task_type=TaskType.TODO,
        notes=notes,
        priority=1.5,
    )

    data = created.get("data", {})
    print("任务创建成功")
    print(f"id: {data.get('id') or data.get('_id')}")
    print(f"text: {data.get('text')}")
    print(f"type: {data.get('type')}")


if __name__ == "__main__":
    run_create_task_test()
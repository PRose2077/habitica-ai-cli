import os
import sys
import json
from typing import List

from pydantic import TypeAdapter

# Ensure `src` is importable so we can import `model.models`
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from model.models import Task, Todo


def test_parse_and_dump_json():
    # 模拟从 API 获取的任务列表
    raw_json = [
        {
            "_id": "task-uuid-123",
            "type": "todo",
            "text": "完成 Python 模型设计",
            "notes": "使用 Pydantic v2",
            "priority": 1.5,
            "completed": False,
            "checklist": [{"id": "item-1", "text": "查阅文档", "completed": True}],
        }
    ]

    adapter = TypeAdapter(List[Task])
    tasks = adapter.validate_python(raw_json)

    assert isinstance(tasks, list)
    assert len(tasks) == 1

    t = tasks[0]
    assert isinstance(t, Todo)
    assert t.text == "完成 Python 模型设计"
    assert t.completed is False
    assert len(t.checklist) == 1
    assert t.checklist[0].text == "查阅文档"

    # 导出为 JSON 并验证内容（TypeAdapter.dump_json 返回 bytes）
    pydantic_json = adapter.dump_json(tasks).decode()
    parsed = json.loads(pydantic_json)
    assert isinstance(parsed, list)
    assert parsed[0]["text"] == "完成 Python 模型设计"


if __name__ == "__main__":
    test_parse_and_dump_json()
    print("tests/test_models.py: OK")

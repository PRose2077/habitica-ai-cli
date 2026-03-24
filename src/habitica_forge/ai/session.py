"""交互式拆解会话管理"""

from dataclasses import dataclass, field
from typing import List, Optional

from habitica_forge.ai.llm_client import SmartDecomposeResult, ChecklistSuggestion


@dataclass
class DecomposeSession:
    """拆解会话状态

    用于管理多轮对话式任务拆解的会话状态，
    包括原始输入、当前结果和对话历史。
    """

    # 原始用户输入
    original_input: str

    # 当前拆解结果
    current_result: SmartDecomposeResult

    # 对话历史 (用于多轮 AI 交互)
    conversation_history: List[dict] = field(default_factory=list)

    # 是否是新创建的任务 (vs 更新现有任务)
    is_new_task: bool = True

    # 现有任务 ID (如果是更新)
    existing_task_id: Optional[str] = None

    def add_user_message(self, content: str) -> None:
        """添加用户消息到历史

        Args:
            content: 用户消息内容
        """
        self.conversation_history.append({"role": "user", "content": content})

    def add_assistant_message(self, content: str) -> None:
        """添加助手消息到历史

        Args:
            content: 助手消息内容
        """
        self.conversation_history.append({"role": "assistant", "content": content})

    def update_checklist(self, checklist: List[ChecklistSuggestion]) -> None:
        """更新子任务列表

        Args:
            checklist: 新的子任务列表
        """
        self.current_result.checklist = checklist

    def update_title(self, title: str) -> None:
        """更新任务标题

        Args:
            title: 新的任务标题
        """
        self.current_result.task_title = title

    def update_notes(self, notes: Optional[str]) -> None:
        """更新任务备注

        Args:
            notes: 新的任务备注
        """
        self.current_result.task_notes = notes

    def update_priority(self, priority: str) -> None:
        """更新建议优先级

        Args:
            priority: 新的建议优先级
        """
        self.current_result.suggested_priority = priority

    def to_json_history(self) -> str:
        """将对话历史转换为 JSON 字符串

        Returns:
            JSON 格式的对话历史
        """
        import json
        return json.dumps(self.conversation_history, ensure_ascii=False, indent=2)
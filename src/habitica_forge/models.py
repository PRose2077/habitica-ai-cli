"""数据模型定义"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

TaskType = Literal["habit", "daily", "todo", "reward"]
AttributeType = Literal["str", "int", "per", "con"]
FrequencyType = Literal["daily", "weekly", "monthly", "yearly"]

ALLOWED_PRIORITIES = (0.1, 1.0, 1.5, 2.0)


class ChecklistItem(BaseModel):
    """Checklist 项"""

    id: Optional[str] = None
    text: str
    completed: bool = False


class ReminderItem(BaseModel):
    """提醒项"""

    id: str
    startDate: str
    time: str


class TaskData(BaseModel):
    """任务数据模型"""

    id: Optional[str] = None
    text: str
    type: TaskType
    tags: List[str] = Field(default_factory=list)
    alias: Optional[str] = None
    attribute: Optional[AttributeType] = None
    checklist: List[ChecklistItem] = Field(default_factory=list)
    collapseChecklist: bool = False
    notes: Optional[str] = None
    date: Optional[datetime] = None
    priority: float = Field(default=1.0, description="任务优先级，允许值为 0.1, 1, 1.5, 2")
    reminders: List[ReminderItem] = Field(default_factory=list)
    frequency: FrequencyType = "weekly"
    repeat: Dict[str, bool] = Field(default_factory=dict)
    everyX: int = 1
    streak: int = 0
    daysOfMonth: List[int] = Field(default_factory=list)
    weeksOfMonth: List[int] = Field(default_factory=list)
    startDate: Optional[datetime] = None
    up: bool = True
    down: bool = True
    value: float = 0
    completed: bool = False
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    userId: Optional[str] = None

    @model_validator(mode="after")
    def validate_task_rules(self) -> "TaskData":
        # 优先级验证（宽松处理）
        if self.priority not in ALLOWED_PRIORITIES:
            # 自动修正到最接近的允许值
            if self.priority < 0.5:
                self.priority = 0.1
            elif self.priority < 1.25:
                self.priority = 1.0
            elif self.priority < 1.75:
                self.priority = 1.5
            else:
                self.priority = 2.0

        # value 不能为负
        if self.value < 0:
            self.value = 0

        return self

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=True)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "TaskData":
        """从 API 响应创建 TaskData"""
        # 处理 checklist
        checklist = []
        for item in data.get("checklist", []):
            checklist.append(
                ChecklistItem(
                    id=item.get("id"),
                    text=item.get("text", ""),
                    completed=item.get("completed", False),
                )
            )

        # 处理日期字段
        date = None
        if data.get("date"):
            try:
                date = datetime.fromisoformat(data["date"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        created_at = None
        if data.get("createdAt"):
            try:
                created_at = datetime.fromisoformat(data["createdAt"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        updated_at = None
        if data.get("updatedAt"):
            try:
                updated_at = datetime.fromisoformat(data["updatedAt"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        start_date = None
        if data.get("startDate"):
            try:
                start_date = datetime.fromisoformat(data["startDate"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return cls(
            id=data.get("id") or data.get("_id"),
            text=data.get("text", ""),
            type=data.get("type", "todo"),
            tags=data.get("tags", []),
            alias=data.get("alias"),
            attribute=data.get("attribute"),
            checklist=checklist,
            collapseChecklist=data.get("collapseChecklist", False),
            notes=data.get("notes"),
            date=date,
            priority=data.get("priority", 1.0),
            reminders=[],
            frequency=data.get("frequency", "weekly"),
            repeat=data.get("repeat", {}),
            everyX=data.get("everyX", 1),
            streak=data.get("streak", 0),
            daysOfMonth=data.get("daysOfMonth", []),
            weeksOfMonth=data.get("weeksOfMonth", []),
            startDate=start_date,
            up=data.get("up", True),
            down=data.get("down", True),
            value=data.get("value", 0),
            completed=data.get("completed", False),
            createdAt=created_at,
            updatedAt=updated_at,
            userId=data.get("userId"),
        )


class TagData(BaseModel):
    """标签数据模型"""

    id: str
    name: str

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "TagData":
        """从 API 响应创建 TagData"""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
        )


class HabiticaAPIResponse(BaseModel):
    """Habitica API 响应模型"""

    success: bool
    data: Optional[Dict[str, Any] | List[Dict[str, Any]]] = None
    error: Optional[str] = None
    message: Optional[str] = None
    notifications: List[Dict[str, Any]] = Field(default_factory=list)
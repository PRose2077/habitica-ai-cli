from typing import List, Optional, Union, Dict, Annotated, Literal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl

# --- 枚举定义 ---

class TaskType(str, Enum):
    HABIT = "habit"
    DAILY = "daily"
    TODO = "todo"
    REWARD = "reward"

class Priority(float, Enum):
    TRIVIAL = 0.1
    EASY = 1.0
    MEDIUM = 1.5
    HARD = 2.0

class Attribute(str, Enum):
    STR = "str"  # 力量
    INT = "int"  # 智力
    PER = "per"  # 感知
    CON = "con"  # 体质

class Frequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

# --- 子组件模型 ---

class ChecklistItem(BaseModel):
    id: str
    text: str
    completed: bool = False

class Reminder(BaseModel):
    id: str
    time: datetime
    startDate: Optional[datetime] = None

# --- 核心任务模型 ---

class TaskBase(BaseModel):
    """所有任务共有的基础字段"""
    id: str = Field(alias="_id")
    text: str  # 任务标题
    notes: Optional[str] = ""  # 任务备注
    value: float = 0.0  # 任务的正负值/进度
    priority: Priority = Priority.EASY
    attribute: Attribute = Attribute.STR
    tags: List[str] = []  # 标签的 UUID 列表
    created_at: Optional[datetime] = Field(None, alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")

class Habit(TaskBase):
    type: Literal["habit"] = TaskType.HABIT.value
    up: bool = True  # 是否有正向按钮
    down: bool = True  # 是否有负向按钮
    counter_up: int = Field(0, alias="counterUp")
    counter_down: int = Field(0, alias="counterDown")
    frequency: Frequency = Frequency.DAILY

class Daily(TaskBase):
    type: Literal["daily"] = TaskType.DAILY.value
    completed: bool = False
    repeat: Dict[str, bool] = Field(default_factory=lambda: {
        "m": True, "t": True, "w": True, "th": True, "f": True, "s": True, "su": True
    })
    streak: int = 0
    days_of_month: List[int] = Field([], alias="daysOfMonth")
    weeks_of_month: List[int] = Field([], alias="weeksOfMonth")
    checklist: List[ChecklistItem] = []
    reminders: List[Reminder] = []

class Todo(TaskBase):
    type: Literal["todo"] = TaskType.TODO.value
    completed: bool = False
    date: Optional[datetime] = None  # 截止日期
    checklist: List[ChecklistItem] = []
    reminders: List[Reminder] = []

class Reward(TaskBase):
    type: Literal["reward"] = TaskType.REWARD.value
    value: float  # 金币消耗

# 使用带判别器的 Annotated Union 实现多态解析（按 `type` 字段判别）
Task = Annotated[Union[Habit, Daily, Todo, Reward], Field(discriminator="type")]

# --- 用户与统计数据模型 ---

class Stats(BaseModel):
    hp: float
    mp: float
    exp: float
    gp: float  # 金币
    lvl: int
    class_name: str = Field(alias="class")

class Profile(BaseModel):
    name: str
    photo: Optional[HttpUrl] = None
    blurb: Optional[str] = None

class User(BaseModel):
    id: str = Field(alias="_id")
    profile: Profile
    stats: Stats
    items: Dict  # 包含装备、坐骑等，结构复杂可进一步细化
    auth: Dict  # 包含 local.username 等信息
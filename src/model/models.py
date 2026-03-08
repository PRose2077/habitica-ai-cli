from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime


class TaskType(Enum):
    HABIT = "habit"
    DAILY = "daily"
    TODO = "todo"
    REWARD = "reward"


class Priority(Enum):
    TRIVIAL = 0.1
    EASY = 1.0
    MEDIUM = 1.5
    HARD = 2.0


class Attribute(Enum):
    STR = "str"
    INT = "int"
    PER = "per"
    CON = "con"


@dataclass
class ChecklistItem:
    id: str
    text: str
    completed: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChecklistItem":
        return cls(id=str(data.get("id") or data.get("_id") or ""), text=data.get("text", ""), completed=bool(data.get("completed", False)))


@dataclass
class Tag:
    id: str
    name: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Tag":
        return cls(id=str(data.get("id") or data.get("_id") or ""), name=data.get("name", ""))


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ")
        except Exception:
            return None


@dataclass
class Task:
    id: str
    text: str
    task_type: TaskType
    notes: Optional[str] = ""
    tags: List[str] = field(default_factory=list)
    priority: float = Priority.EASY.value
    attribute: str = Attribute.STR.value
    challenge: Dict[str, str] = field(default_factory=dict)
    completed: bool = False
    date: Optional[str] = None
    checklist: List[ChecklistItem] = field(default_factory=list)
    up: bool = True
    down: bool = True
    value: float = 0.0
    streak: int = 0
    frequency: str = "weekly"
    everyX: int = 1
    repeat: Dict[str, bool] = field(default_factory=dict)
    cost: float = 0.0
    updated_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        ttype = data.get("type") or data.get("task_type")
        try:
            task_type = TaskType(ttype)
        except Exception:
            task_type = TaskType.TODO

        checklist_raw = data.get("checklist") or []
        checklist = [ChecklistItem.from_dict(it) for it in checklist_raw]

        tags_raw = data.get("tags") or []
        tags = [str(t) for t in tags_raw]

        updated_at = _parse_iso(data.get("updatedAt") or data.get("updated_at"))

        return cls(
            id=str(data.get("id") or data.get("_id") or ""),
            text=data.get("text", ""),
            task_type=task_type,
            notes=data.get("notes", ""),
            tags=tags,
            priority=float(data.get("priority") or Priority.EASY.value),
            attribute=str(data.get("attribute") or Attribute.STR.value),
            challenge=data.get("challenge", {}) or {},
            completed=bool(data.get("completed", False)),
            date=data.get("date") or data.get("dueDate"),
            checklist=checklist,
            up=bool(data.get("up", True)),
            down=bool(data.get("down", True)),
            value=float(data.get("value") or 0.0),
            streak=int(data.get("streak", 0)),
            frequency=str(data.get("frequency", "weekly")),
            everyX=int(data.get("everyX", 1)),
            repeat=data.get("repeat", {}) or {},
            cost=float(data.get("cost", 0.0)),
            updated_at=updated_at,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "type": self.task_type.value,
            "notes": self.notes,
            "tags": self.tags,
            "priority": self.priority,
            "attribute": self.attribute,
            "completed": self.completed,
            "date": self.date,
            "checklist": [vars(c) for c in self.checklist],
            "up": self.up,
            "down": self.down,
            "value": self.value,
            "streak": self.streak,
            "frequency": self.frequency,
            "everyX": self.everyX,
            "repeat": self.repeat,
            "cost": self.cost,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class User:
    id: str
    api_token: str
    name: str
    level: int = 1
    hp: float = 50.0
    mp: float = 0.0
    exp: int = 0
    gp: float = 0.0
    day_start: int = 0
    is_sleeping: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        return cls(
            id=str(data.get("id") or data.get("_id") or ""),
            api_token=str(data.get("api_token") or data.get("apiToken") or ""),
            name=str(data.get("profile", {}).get("name") or data.get("name") or ""),
            level=int(data.get("stats", {}).get("lvl", data.get("level", 1))),
            hp=float(data.get("stats", {}).get("hp", data.get("hp", 50.0))),
            mp=float(data.get("stats", {}).get("mp", data.get("mp", 0.0))),
            exp=int(data.get("stats", {}).get("exp", data.get("exp", 0))),
            gp=float(data.get("stats", {}).get("gp", data.get("gp", 0.0))),
            day_start=int(data.get("preferences", {}).get("dayStart", data.get("day_start", 0))),
            is_sleeping=bool(data.get("party", {}).get("quest", {}).get("progress", False)),
        )

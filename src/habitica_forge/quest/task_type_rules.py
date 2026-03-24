"""任务类型专属游戏化规则

为 Habit/Daily/Todo 建立各自的游戏化策略：

- Habit: 诱惑/克制、训练/堕落、正负反馈
- Daily: 巡逻、仪式、例行职责、守护循环
- Todo: 委托、任务书、战役、支线/主线

这些规则会影响 AI 生成游戏化内容时的语气和风格。
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from habitica_forge.quest.archetype import QuestArchetype


class TaskTypeCategory(str, Enum):
    """任务类型分类"""

    HABIT = "habit"
    DAILY = "daily"
    TODO = "todo"
    REWARD = "reward"


class TaskTypeGamificationConfig(BaseModel):
    """任务类型游戏化配置

    定义每种任务类型的游戏化规则。
    """

    # 类型名称
    name: str = Field(..., description="类型名称")
    display_name: str = Field(..., description="显示名称")

    # 核心概念
    core_concept: str = Field(..., description="核心概念描述")
    game_terminology: List[str] = Field(
        default_factory=list,
        description="游戏术语（如：委托、巡逻、训练）"
    )

    # 风格化命名模板
    fantasy_template: str = Field(
        default="",
        description="奇幻风格命名模板"
    )
    cyberpunk_template: str = Field(
        default="",
        description="赛博风格命名模板"
    )
    wuxia_template: str = Field(
        default="",
        description="武侠风格命名模板"
    )
    normal_template: str = Field(
        default="",
        description="正常风格命名模板"
    )

    # 语气和反馈
    tone: str = Field(
        default="neutral",
        description="默认语气"
    )
    positive_feedback_templates: List[str] = Field(
        default_factory=list,
        description="正向反馈模板"
    )
    negative_feedback_templates: List[str] = Field(
        default_factory=list,
        description="负向反馈模板（主要用于 Habit）"
    )

    # 原型偏好（某些类型更适合某些原型）
    preferred_archetypes: List[QuestArchetype] = Field(
        default_factory=list,
        description="适合的原型"
    )


# ============================================
# 任务类型配置
# ============================================

HABIT_CONFIG = TaskTypeGamificationConfig(
    name="habit",
    display_name="习惯",
    core_concept="训练/克制、正负反馈、持续成长",
    game_terminology=["训练", "修炼", "克制", "诱惑", "养成", "堕落"],
    fantasy_template="{action} · {concept}",
    cyberpunk_template="{action} // {concept}",
    wuxia_template="{action} · {concept}",
    normal_template="{action} {concept}",
    tone="encouraging",
    positive_feedback_templates=[
        "坚持{streak}天！继续修炼！",
        "意志坚定，心性提升！",
        "训练有成，实力见长！",
    ],
    negative_feedback_templates=[
        "今日未行，不可松懈",
        "修行中断，当自省察",
        "诱惑当前，需更坚定",
    ],
    preferred_archetypes=[
        QuestArchetype.LEARN,
        QuestArchetype.CLEANUP,
        QuestArchetype.BATTLE,
    ]
)

DAILY_CONFIG = TaskTypeGamificationConfig(
    name="daily",
    display_name="每日任务",
    core_concept="巡逻、仪式、例行职责、守护循环",
    game_terminology=["巡逻", "守护", "仪式", "例行", "循环", "维护"],
    fantasy_template="【{location}】{action}",
    cyberpunk_template="[{location}] {action}",
    wuxia_template="【{location}】{action}",
    normal_template="{action}",
    tone="steady",
    positive_feedback_templates=[
        "巡逻完成，领地安宁！",
        "例行职责已履行！",
        "守护连胜{streak}天！",
    ],
    negative_feedback_templates=[
        "今日巡逻未完，警戒不可松懈",
        "例行事务延误，秩序受损",
    ],
    preferred_archetypes=[
        QuestArchetype.CLEANUP,
        QuestArchetype.REPAIR,
        QuestArchetype.COMMUNICATE,
    ]
)

TODO_CONFIG = TaskTypeGamificationConfig(
    name="todo",
    display_name="待办任务",
    core_concept="委托、任务书、战役、支线/主线",
    game_terminology=["委托", "任务", "任务书", "战役", "支线", "主线", "远征"],
    fantasy_template="【{priority}】{title}",
    cyberpunk_template="[{priority}] {title}",
    wuxia_template="【{priority}】{title}",
    normal_template="{title}",
    tone="quest",
    positive_feedback_templates=[
        "委托完成！战利品已入账！",
        "任务达成！声望提升！",
        "战役胜利！荣誉加身！",
    ],
    negative_feedback_templates=[
        "委托超时，声誉受损",
        "任务延误，错失良机",
    ],
    preferred_archetypes=[
        QuestArchetype.CRAFT,
        QuestArchetype.EXPLORE,
        QuestArchetype.COMMUNICATE,
        QuestArchetype.BATTLE,
    ]
)

REWARD_CONFIG = TaskTypeGamificationConfig(
    name="reward",
    display_name="奖励",
    core_concept="战利品、奖励、自我激励",
    game_terminology=["战利品", "奖励", "宝箱", "奖励"],
    fantasy_template="【奖励】{title}",
    cyberpunk_template="[奖励] {title}",
    wuxia_template="【奖励】{title}",
    normal_template="奖励：{title}",
    tone="celebration",
    positive_feedback_templates=[
        "战利品已领取！",
        "奖励解锁！",
    ],
    negative_feedback_templates=[],
    preferred_archetypes=[],
)


# 类型配置映射
TASK_TYPE_CONFIGS: Dict[TaskTypeCategory, TaskTypeGamificationConfig] = {
    TaskTypeCategory.HABIT: HABIT_CONFIG,
    TaskTypeCategory.DAILY: DAILY_CONFIG,
    TaskTypeCategory.TODO: TODO_CONFIG,
    TaskTypeCategory.REWARD: REWARD_CONFIG,
}


# ============================================
# 工具函数
# ============================================

def get_task_type_config(task_type: str) -> TaskTypeGamificationConfig:
    """获取任务类型配置

    Args:
        task_type: 任务类型 (habit/daily/todo/reward)

    Returns:
        任务类型配置
    """
    try:
        category = TaskTypeCategory(task_type.lower())
        return TASK_TYPE_CONFIGS.get(category, TODO_CONFIG)
    except ValueError:
        return TODO_CONFIG


def get_task_type_template(task_type: str, style: str) -> str:
    """获取任务类型的命名模板

    Args:
        task_type: 任务类型
        style: 风格名称

    Returns:
        命名模板
    """
    config = get_task_type_config(task_type)
    style = style.lower()

    if style == "fantasy":
        return config.fantasy_template or config.normal_template
    elif style == "cyberpunk":
        return config.cyberpunk_template or config.normal_template
    elif style == "wuxia":
        return config.wuxia_template or config.normal_template
    else:
        return config.normal_template


def get_positive_feedback(task_type: str, streak: int = 0) -> str:
    """获取正向反馈文案

    Args:
        task_type: 任务类型
        streak: 连续天数（用于 Daily/Habit）

    Returns:
        反馈文案
    """
    config = get_task_type_config(task_type)
    templates = config.positive_feedback_templates

    if not templates:
        return "任务完成！"

    import random
    template = random.choice(templates)
    return template.format(streak=streak) if "{streak}" in template else template


def get_negative_feedback(task_type: str) -> str:
    """获取负向反馈文案

    Args:
        task_type: 任务类型

    Returns:
        反馈文案
    """
    config = get_task_type_config(task_type)
    templates = config.negative_feedback_templates

    if not templates:
        return "任务未完成"

    import random
    return random.choice(templates)


def get_game_terminology(task_type: str, style: str = "normal") -> List[str]:
    """获取游戏术语列表

    Args:
        task_type: 任务类型
        style: 风格名称

    Returns:
        游戏术语列表
    """
    config = get_task_type_config(task_type)
    return config.game_terminology


def is_preferred_archetype(task_type: str, archetype: QuestArchetype) -> bool:
    """检查原型是否适合该任务类型

    Args:
        task_type: 任务类型
        archetype: 任务原型

    Returns:
        是否适合
    """
    config = get_task_type_config(task_type)
    return archetype in config.preferred_archetypes


# ============================================
# 任务类型特定的游戏化规则
# ============================================

class HabitGamificationRules:
    """Habit 类型游戏化规则

    Habit 的核心特征是正负双向反馈：
    - 正向行为 (+): 训练、成长、提升
    - 负向行为 (-): 诱惑、堕落、放纵

    游戏化时需要：
    - 强调行为的意义和影响
    - 为正负行为提供不同的叙事
    - 鼓励持续坚持
    """

    # 正向行为主题
    POSITIVE_THEMES = {
        "fantasy": ["修炼", "淬炼", "提升", "净化", "强化"],
        "cyberpunk": ["优化", "升级", "加载", "编译", "训练"],
        "wuxia": ["修炼", "精进", "淬炼", "悟道", "参悟"],
        "normal": ["坚持", "培养", "养成", "练习"],
    }

    # 负向行为主题
    NEGATIVE_THEMES = {
        "fantasy": ["堕落", "放纵", "沉沦", "腐化"],
        "cyberpunk": ["过载", "崩溃", "感染", "故障"],
        "wuxia": ["心魔", "走火入魔", "堕落", "迷失"],
        "normal": ["克制", "避免", "减少"],
    }

    @classmethod
    def get_positive_theme(cls, style: str = "normal") -> List[str]:
        """获取正向行为主题词"""
        return cls.POSITIVE_THEMES.get(style, cls.POSITIVE_THEMES["normal"])

    @classmethod
    def get_negative_theme(cls, style: str = "normal") -> List[str]:
        """获取负向行为主题词"""
        return cls.NEGATIVE_THEMES.get(style, cls.NEGATIVE_THEMES["normal"])


class DailyGamificationRules:
    """Daily 类型游戏化规则

    Daily 的核心特征是循环和守护：
    - 每日重复的职责
    - 连续性带来成就感
    - 失败会带来损失感

    游戏化时需要：
    - 强调"守护"、"巡逻"的感觉
    - 突出连续性（连击、连胜）
    - 赋予例行事务意义
    """

    # 连击主题
    STREAK_THEMES = {
        "fantasy": ["守护", "巡逻", "坚持", "维持", "守护"],
        "cyberpunk": ["运行", "同步", "维持", "稳定", "守护"],
        "wuxia": ["修行", "坚持", "精进", "悟道", "参悟"],
        "normal": ["坚持", "连续", "完成", "维持"],
    }

    # 失败主题
    BREAK_THEMES = {
        "fantasy": ["失守", "中断", "秩序崩坏"],
        "cyberpunk": ["断连", "异常", "系统不稳定"],
        "wuxia": ["修行中断", "心境动摇", "气机紊乱"],
        "normal": ["中断", "未完成"],
    }

    @classmethod
    def get_streak_message(cls, streak: int, style: str = "normal") -> str:
        """获取连击消息"""
        themes = cls.STREAK_THEMES.get(style, cls.STREAK_THEMES["normal"])
        import random
        theme = random.choice(themes)
        return f"{theme}连胜 {streak} 天！"

    @classmethod
    def get_break_message(cls, style: str = "normal") -> str:
        """获取中断消息"""
        themes = cls.BREAK_THEMES.get(style, cls.BREAK_THEMES["normal"])
        import random
        return random.choice(themes)


class TodoGamificationRules:
    """Todo 类型游戏化规则

    Todo 的核心特征是委托和任务：
    - 有明确的开始和结束
    - 可以有复杂度和优先级
    - 支持主线/支线/传奇任务

    游戏化时需要：
    - 像"任务委托"一样呈现
    - 根据难度/复杂度区分
    - 支持系列任务和章节化
    """

    # 优先级主题
    PRIORITY_THEMES = {
        "trivial": {
            "fantasy": "杂务",
            "cyberpunk": "微任务",
            "wuxia": "杂事",
            "normal": "简单",
        },
        "easy": {
            "fantasy": "委托",
            "cyberpunk": "任务",
            "wuxia": "事务",
            "normal": "普通",
        },
        "medium": {
            "fantasy": "重要委托",
            "cyberpunk": "优先任务",
            "wuxia": "要事",
            "normal": "重要",
        },
        "hard": {
            "fantasy": "传奇委托",
            "cyberpunk": "核心任务",
            "wuxia": "大事",
            "normal": "紧急",
        },
    }

    # 任务类型标记
    QUEST_MARKERS = {
        "fantasy": {"main": "【主线】", "side": "【支线】", "legendary": "【传奇】"},
        "cyberpunk": {"main": "[主线]", "side": "[支线]", "legendary": "[传奇]"},
        "wuxia": {"main": "【主线】", "side": "【支线】", "legendary": "【传奇】"},
        "normal": {"main": "[主线]", "side": "[支线]", "legendary": "[传奇]"},
    }

    @classmethod
    def get_priority_label(cls, priority: str, style: str = "normal") -> str:
        """获取优先级标签"""
        priority_config = cls.PRIORITY_THEMES.get(priority, cls.PRIORITY_THEMES["easy"])
        return priority_config.get(style, priority_config["normal"])

    @classmethod
    def get_quest_marker(cls, quest_type: str, style: str = "normal") -> str:
        """获取任务类型标记"""
        markers = cls.QUEST_MARKERS.get(style, cls.QUEST_MARKERS["normal"])
        return markers.get(quest_type, "")
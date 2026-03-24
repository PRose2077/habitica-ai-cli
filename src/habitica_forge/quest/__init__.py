"""V2 任务游戏化语义层

这个模块实现了 V2 的核心抽象：
- 任务原型 (Quest Archetypes)
- 任务类型专属规则
- 游戏化可读性约束

V2 阶段四：
- 传奇任务系统 (Legendary Quests)
- 任务链/系列任务

V2 阶段五改进：
- 使用 Tags 替代 notes 中的元数据存储
- 简化双名结构
"""

from habitica_forge.quest.archetype import (
    ArchetypeConfig,
    ArchetypeKeywords,
    QuestArchetype,
    detect_archetype_from_text,
    get_archetype_config,
    get_style_nouns,
    get_style_verbs,
)
from habitica_forge.quest.legendary import (
    LegendaryConfig,
    LegendaryDetector,
    LegendaryType,
    QuestChain,
    QuestChainManager,
    get_chain_manager,
)
from habitica_forge.quest.tags import (
    ForgeTagPrefix,
    ForgeTags,
    LEGENDARY_TAG,
    LEGENDARY_TAG_NAMES,
    ARCHETYPE_TAG_NAMES,
    build_forge_tags_from_result,
    ensure_tags_exist,
    get_tag_ids_for_forge_tags,
    parse_forge_tags,
)
from habitica_forge.quest.task_type_rules import (
    DailyGamificationRules,
    HabitGamificationRules,
    TaskTypeCategory,
    TaskTypeGamificationConfig,
    TodoGamificationRules,
    get_game_terminology,
    get_negative_feedback,
    get_positive_feedback,
    get_task_type_config,
    get_task_type_template,
    is_preferred_archetype,
)
from habitica_forge.quest.validator import (
    DEFAULT_MAX_TITLE_LENGTH,
    truncate_title,
)

__all__ = [
    # 原型相关
    "QuestArchetype",
    "ArchetypeConfig",
    "ArchetypeKeywords",
    "detect_archetype_from_text",
    "get_archetype_config",
    "get_style_verbs",
    "get_style_nouns",
    # Tags 相关 (V2 阶段五)
    "ForgeTagPrefix",
    "ForgeTags",
    "LEGENDARY_TAG",
    "LEGENDARY_TAG_NAMES",
    "ARCHETYPE_TAG_NAMES",
    "build_forge_tags_from_result",
    "ensure_tags_exist",
    "get_tag_ids_for_forge_tags",
    "parse_forge_tags",
    # 任务类型规则
    "TaskTypeCategory",
    "TaskTypeGamificationConfig",
    "HabitGamificationRules",
    "DailyGamificationRules",
    "TodoGamificationRules",
    "get_task_type_config",
    "get_task_type_template",
    "get_positive_feedback",
    "get_negative_feedback",
    "get_game_terminology",
    "is_preferred_archetype",
    # 验证器
    "DEFAULT_MAX_TITLE_LENGTH",
    "truncate_title",
    # 传奇任务系统
    "LegendaryType",
    "LegendaryConfig",
    "LegendaryDetector",
    "QuestChain",
    "QuestChainManager",
    "get_chain_manager",
]
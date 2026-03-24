"""职业倾向系统

V2 阶段五新增：
- 基于用户近期任务分布生成职业倾向
- 职业倾向随风格系统变化
- 作为轻量、动态身份层

职业倾向不替代称号墙，而是作为动态身份展示。
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from habitica_forge.quest.archetype import QuestArchetype
from habitica_forge.styles import get_style_config
from habitica_forge.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ProfessionTendency:
    """职业倾向数据"""

    name: str  # 职业名称
    display_name: str  # 显示名称
    description: str  # 描述
    dominant_archetypes: List[str]  # 主导原型
    score: float  # 倾向分数 (0-100)
    level: int  # 等级 (1-5)


# 职业定义 - 基于任务原型组合
PROFESSION_DEFINITIONS = {
    # 单一原型主导的职业
    "scribe": {
        "display_name": "抄写员",
        "description": "专注文档与沟通",
        "archetypes": ["communicate", "craft"],
        "min_score": 30,
    },
    "archivist": {
        "display_name": "档案猎人",
        "description": "整理与分类专家",
        "archetypes": ["cleanup", "explore"],
        "min_score": 30,
    },
    "artificer": {
        "display_name": "工匠",
        "description": "制造与修复专家",
        "archetypes": ["craft", "repair"],
        "min_score": 30,
    },
    "seeker": {
        "display_name": "探索者",
        "description": "学习与发现先锋",
        "archetypes": ["explore", "learn"],
        "min_score": 30,
    },
    "guardian": {
        "display_name": "守护者",
        "description": "清理与维护卫士",
        "archetypes": ["cleanup", "supply"],
        "min_score": 30,
    },
    "warrior": {
        "display_name": "战士",
        "description": "挑战与攻克能手",
        "archetypes": ["battle", "repair"],
        "min_score": 30,
    },
    "merchant": {
        "display_name": "商人",
        "description": "采购与补给专家",
        "archetypes": ["supply", "communicate"],
        "min_score": 30,
    },
    "sage": {
        "display_name": "贤者",
        "description": "学习与研究大师",
        "archetypes": ["learn", "explore"],
        "min_score": 40,
    },
    # 高级组合职业
    "battle_mage": {
        "display_name": "战斗法师",
        "description": "学习与战斗双修",
        "archetypes": ["learn", "battle"],
        "min_score": 35,
    },
    "master_craftsman": {
        "display_name": "工匠大师",
        "description": "制造与学习结合",
        "archetypes": ["craft", "learn"],
        "min_score": 35,
    },
    "commander": {
        "display_name": "指挥官",
        "description": "沟通与战斗领袖",
        "archetypes": ["communicate", "battle"],
        "min_score": 35,
    },
    # 综合职业
    "adventurer": {
        "display_name": "冒险者",
        "description": "全能型任务者",
        "archetypes": ["explore", "battle", "craft"],
        "min_score": 25,
    },
    "keeper": {
        "display_name": "守望者",
        "description": "维护与清理专家",
        "archetypes": ["cleanup", "repair", "supply"],
        "min_score": 25,
    },
}

# 风格化的职业名称映射
STYLE_PROFESSION_NAMES = {
    "fantasy": {
        "scribe": "文书法师",
        "archivist": "卷轴守护者",
        "artificer": "附魔工匠",
        "seeker": "秘境探索者",
        "guardian": "圣殿守护者",
        "warrior": "战神侍从",
        "merchant": "贸易公会成员",
        "sage": "大贤者",
        "battle_mage": "战斗法师",
        "master_craftsman": "神匠",
        "commander": "军团指挥官",
        "adventurer": "传奇冒险者",
        "keeper": "圣域守望者",
    },
    "cyberpunk": {
        "scribe": "数据录入员",
        "archivist": "数据挖掘者",
        "artificer": "系统工程师",
        "seeker": "网络探索者",
        "guardian": "安全守护者",
        "warrior": "网络战士",
        "merchant": "数据贩子",
        "sage": "超级黑客",
        "battle_mage": "战斗程序员",
        "master_craftsman": "系统架构师",
        "commander": "项目经理",
        "adventurer": "自由职业者",
        "keeper": "系统维护员",
    },
    "wuxia": {
        "scribe": "江湖文书",
        "archivist": "典籍守护者",
        "artificer": "神兵铸造师",
        "seeker": "武学探索者",
        "guardian": "门派守护者",
        "warrior": "武林高手",
        "merchant": "江湖商贾",
        "sage": "武学宗师",
        "battle_mage": "内功高手",
        "master_craftsman": "锻造宗师",
        "commander": "帮派掌门",
        "adventurer": "江湖侠客",
        "keeper": "门派管家",
    },
}


class ProfessionAnalyzer:
    """职业倾向分析器"""

    def __init__(self, style: str = "normal"):
        """初始化分析器

        Args:
            style: 当前风格
        """
        self.style = style
        self._archetype_counts: Dict[str, int] = {}
        self._total_tasks = 0

    def add_task(self, archetype: Optional[str]) -> None:
        """添加任务到分析

        Args:
            archetype: 任务原型
        """
        if archetype:
            self._archetype_counts[archetype] = self._archetype_counts.get(archetype, 0) + 1
            self._total_tasks += 1

    def add_tasks(self, archetypes: List[Optional[str]]) -> None:
        """批量添加任务

        Args:
            archetypes: 任务原型列表
        """
        for archetype in archetypes:
            self.add_task(archetype)

    def calculate_scores(self) -> Dict[str, float]:
        """计算各原型分数

        Returns:
            原型分数字典 (0-100)
        """
        if self._total_tasks == 0:
            return {}

        scores = {}
        for archetype, count in self._archetype_counts.items():
            scores[archetype] = (count / self._total_tasks) * 100

        return scores

    def detect_profession(self) -> Optional[ProfessionTendency]:
        """检测职业倾向

        Returns:
            检测到的职业倾向，无匹配时返回 None
        """
        scores = self.calculate_scores()

        if not scores:
            return None

        # 计算每个职业的匹配分数
        profession_scores = []

        for prof_key, prof_def in PROFESSION_DEFINITIONS.items():
            archetypes = prof_def["archetypes"]
            min_score = prof_def["min_score"]

            # 计算匹配分数：所有指定原型的分数之和
            match_score = sum(scores.get(a, 0) for a in archetypes)

            # 检查是否达到最低门槛
            if match_score >= min_score:
                profession_scores.append((prof_key, match_score))

        if not profession_scores:
            # 如果没有匹配的职业，返回最高分数的原型对应职业
            top_archetype = max(scores.items(), key=lambda x: x[1])[0]
            return self._archetype_to_default_profession(top_archetype, scores[top_archetype])

        # 返回分数最高的职业
        profession_scores.sort(key=lambda x: x[1], reverse=True)
        prof_key, score = profession_scores[0]

        return self._create_profession_tendency(prof_key, score)

    def _create_profession_tendency(
        self, profession_key: str, score: float
    ) -> ProfessionTendency:
        """创建职业倾向对象

        Args:
            profession_key: 职业键
            score: 匹配分数

        Returns:
            职业倾向对象
        """
        prof_def = PROFESSION_DEFINITIONS.get(profession_key, {})

        # 获取风格化的名称
        style_names = STYLE_PROFESSION_NAMES.get(self.style, {})
        display_name = style_names.get(profession_key, prof_def.get("display_name", profession_key))

        # 计算等级 (1-5)
        level = min(5, max(1, int(score / 20) + 1))

        return ProfessionTendency(
            name=profession_key,
            display_name=display_name,
            description=prof_def.get("description", ""),
            dominant_archetypes=prof_def.get("archetypes", []),
            score=score,
            level=level,
        )

    def _archetype_to_default_profession(
        self, archetype: str, score: float
    ) -> ProfessionTendency:
        """将单个原型映射到默认职业

        Args:
            archetype: 原型名称
            score: 分数

        Returns:
            默认职业倾向
        """
        # 原型到职业的默认映射
        archetype_to_profession = {
            "cleanup": "guardian",
            "repair": "artificer",
            "explore": "seeker",
            "craft": "artificer",
            "communicate": "scribe",
            "learn": "seeker",
            "battle": "warrior",
            "supply": "merchant",
        }

        prof_key = archetype_to_profession.get(archetype, "adventurer")
        return self._create_profession_tendency(prof_key, score)


def analyze_profession_tendency(
    tasks: List[Dict],
    style: str = "normal",
) -> Optional[ProfessionTendency]:
    """分析任务列表生成职业倾向

    Args:
        tasks: 任务列表，每个任务应包含 archetype 字段
        style: 当前风格

    Returns:
        检测到的职业倾向
    """
    analyzer = ProfessionAnalyzer(style)

    for task in tasks:
        archetype = task.get("archetype")
        analyzer.add_task(archetype)

    return analyzer.detect_profession()


def get_profession_display_name(profession_key: str, style: str = "normal") -> str:
    """获取风格化的职业名称

    Args:
        profession_key: 职业键
        style: 风格名称

    Returns:
        显示名称
    """
    style_names = STYLE_PROFESSION_NAMES.get(style, {})
    if profession_key in style_names:
        return style_names[profession_key]

    prof_def = PROFESSION_DEFINITIONS.get(profession_key, {})
    return prof_def.get("display_name", profession_key)
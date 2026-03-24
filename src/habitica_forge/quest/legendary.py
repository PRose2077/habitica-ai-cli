"""传奇任务系统

实现 V2 阶段四的传奇任务与任务链系统：
- 传奇任务判定规则
- 专属前缀与标记
- 任务链/系列任务支持
- 任务链持久化存储

V2 阶段五改进：
- 移除元数据依赖，使用外部传入的传奇状态

传奇任务定义：
- 超过 5 个子任务的复杂任务
- 需要多日完成的长期任务
- 用户显式指定的高级任务
"""

import json
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from habitica_forge.utils.logger import get_logger

logger = get_logger(__name__)

# 任务链存储目录
CHAINS_DIR = Path.home() / ".habitica_forge" / "chains"
CHAINS_FILE = CHAINS_DIR / "chains.json"


class LegendaryType(str, Enum):
    """传奇任务类型

    不同类型的传奇任务有不同的前缀和语气。
    """

    MAIN = "main"            # 主线任务：重要且紧急
    EXPEDITION = "expedition"  # 远征任务：长期探索
    CAMPAIGN = "campaign"    # 战役任务：多阶段挑战
    ESCORT = "escort"        # 护送任务：需要持续关注
    SAGA = "saga"            # 史诗任务：超长期项目
    CHAIN = "chain"          # 任务链：系列关联任务


# 传奇任务专属前缀配置
LEGENDARY_PREFIXES = {
    LegendaryType.MAIN: {
        "fantasy": ["【主线】", "【王命】", "【史诗】"],
        "cyberpunk": ["【核心】", "【主节点】", "【关键任务】"],
        "wuxia": ["【主线】", "【门派之托】", "【江湖重任】"],
        "normal": ["【主线】", "【重要】", "【优先】"],
    },
    LegendaryType.EXPEDITION: {
        "fantasy": ["【远征】", "【探索】", "【冒险】"],
        "cyberpunk": ["【远征】", "【深度潜入】", "【数据挖掘】"],
        "wuxia": ["【远行】", "【寻访】", "【踏遍江湖】"],
        "normal": ["【远征】", "【长期项目】"],
    },
    LegendaryType.CAMPAIGN: {
        "fantasy": ["【战役】", "【大战】", "【征讨】"],
        "cyberpunk": ["【战役】", "【系统攻坚】", "【核心破解】"],
        "wuxia": ["【决战】", "【大会】", "【武林盛事】"],
        "normal": ["【战役】", "【多阶段】"],
    },
    LegendaryType.ESCORT: {
        "fantasy": ["【护送】", "【守护】", "【押运】"],
        "cyberpunk": ["【护送】", "【数据传输】", "【安全协议】"],
        "wuxia": ["【护送】", "【押镖】", "【保驾护航】"],
        "normal": ["【持续关注】", "【需要跟进】"],
    },
    LegendaryType.SAGA: {
        "fantasy": ["【史诗】", "【传奇】", "【神话】"],
        "cyberpunk": ["【史诗】", "【超算级】", "【底层重构】"],
        "wuxia": ["【传世】", "【千秋】", "【一代宗师】"],
        "normal": ["【史诗】", "【长期项目】"],
    },
    LegendaryType.CHAIN: {
        "fantasy": ["【任务链】", "【系列】", "【篇章】"],
        "cyberpunk": ["【任务链】", "【关联任务】", "【程序组】"],
        "wuxia": ["【系列】", "【连环】", "【一脉相承】"],
        "normal": ["【系列】", "【任务链】"],
    },
}


class LegendaryConfig(BaseModel):
    """传奇任务配置"""

    type: LegendaryType = Field(
        LegendaryType.MAIN,
        description="传奇任务类型"
    )
    prefix: Optional[str] = Field(
        None,
        description="自定义前缀（优先于默认前缀）"
    )
    estimated_days: Optional[int] = Field(
        None,
        description="预计完成天数"
    )
    milestone_count: int = Field(
        0,
        description="里程碑数量"
    )
    series_name: Optional[str] = Field(
        None,
        description="所属系列名称"
    )
    series_index: Optional[int] = Field(
        None,
        description="系列中的序号"
    )
    chapter_count: int = Field(
        0,
        description="章节数量"
    )


class LegendaryDetector:
    """传奇任务检测器

    根据任务特征判断是否为传奇任务，并确定类型。
    """

    # 判定阈值
    MIN_CHECKLIST_FOR_LEGENDARY = 5  # 子任务数阈值
    MIN_DAYS_FOR_LONG_TASK = 3       # 长期任务天数阈值
    COMPLEX_KEYWORDS = [             # 复杂任务关键词
        "项目", "计划", "完成", "构建", "实现",
        "重构", "迁移", "设计", "开发", "研究",
    ]

    def __init__(self, style: str = "normal"):
        """初始化检测器

        Args:
            style: 当前风格
        """
        self.style = style

    def detect(
        self,
        title: str,
        checklist_count: int = 0,
        notes: Optional[str] = None,
        is_legendary: bool = False,
        legendary_type: Optional[str] = None,
        chain_name: Optional[str] = None,
        user_specified: Optional[str] = None,
    ) -> Tuple[bool, Optional[LegendaryConfig]]:
        """检测任务是否为传奇任务

        Args:
            title: 任务标题
            checklist_count: 子任务数量
            notes: 任务备注
            is_legendary: 是否已标记为传奇任务（从 tags 获取）
            legendary_type: 传奇任务类型（从 tags 获取）
            chain_name: 任务链名称（从 tags 获取）
            user_specified: 用户指定的类型

        Returns:
            (是否传奇任务, 传奇配置)
        """
        # 1. 用户显式指定
        if user_specified:
            legendary_type_parsed = self._parse_user_specified(user_specified)
            if legendary_type_parsed:
                config = LegendaryConfig(type=legendary_type_parsed)
                logger.info(f"User specified legendary type: {legendary_type_parsed}")
                return True, config

        # 2. 检查已有的传奇状态（从 tags 获取）
        if is_legendary:
            config = LegendaryConfig(
                type=self._legendary_type_str_to_enum(legendary_type),
                series_name=chain_name,
            )
            return True, config

        # 3. 基于规则判定
        checklist_score = 0
        keyword_score = 0
        notes_score = 0

        # 子任务数量评分
        if checklist_count >= self.MIN_CHECKLIST_FOR_LEGENDARY:
            checklist_score = min(checklist_count / 3, 3)  # 最高 3 分
        elif checklist_count >= 3:
            checklist_score = 1

        # 关键词评分
        title_lower = title.lower()
        for keyword in self.COMPLEX_KEYWORDS:
            if keyword in title_lower:
                keyword_score += 1
        keyword_score = min(keyword_score, 2)  # 最高 2 分

        # 备注长度评分
        if notes and len(notes) > 200:
            notes_score = 1

        # 综合评分
        total_score = checklist_score + keyword_score + notes_score

        # 评分 >= 3 认为是传奇任务
        if total_score >= 3:
            legendary_type = self._determine_type(
                title=title,
                checklist_count=checklist_count,
                keyword_score=keyword_score,
            )
            config = LegendaryConfig(
                type=legendary_type,
                milestone_count=self._estimate_milestones(checklist_count),
            )
            logger.info(
                f"Detected legendary task (score={total_score}): {title[:30]}..."
            )
            return True, config

        return False, None

    def _parse_user_specified(self, specified: str) -> Optional[LegendaryType]:
        """解析用户指定的类型"""
        specified_lower = specified.lower().strip()

        type_mapping = {
            "主线": LegendaryType.MAIN,
            "main": LegendaryType.MAIN,
            "远征": LegendaryType.EXPEDITION,
            "expedition": LegendaryType.EXPEDITION,
            "战役": LegendaryType.CAMPAIGN,
            "campaign": LegendaryType.CAMPAIGN,
            "护送": LegendaryType.ESCORT,
            "escort": LegendaryType.ESCORT,
            "史诗": LegendaryType.SAGA,
            "saga": LegendaryType.SAGA,
            "链": LegendaryType.CHAIN,
            "chain": LegendaryType.CHAIN,
            "系列": LegendaryType.CHAIN,
        }

        for key, legendary_type in type_mapping.items():
            if key in specified_lower:
                return legendary_type

        return None

    def _quest_type_to_legendary(
        self, quest_type: Optional[str]
    ) -> LegendaryType:
        """将 quest_type 转换为 LegendaryType"""
        mapping = {
            "main": LegendaryType.MAIN,
            "legendary": LegendaryType.SAGA,
            "side": None,
        }
        return mapping.get(quest_type, LegendaryType.MAIN)

    def _legendary_type_str_to_enum(
        self, legendary_type_str: Optional[str]
    ) -> LegendaryType:
        """将传奇类型字符串转换为 LegendaryType 枚举"""
        if not legendary_type_str:
            return LegendaryType.MAIN

        mapping = {
            "main": LegendaryType.MAIN,
            "expedition": LegendaryType.EXPEDITION,
            "campaign": LegendaryType.CAMPAIGN,
            "escort": LegendaryType.ESCORT,
            "saga": LegendaryType.SAGA,
            "chain": LegendaryType.CHAIN,
        }
        return mapping.get(legendary_type_str.lower(), LegendaryType.MAIN)

    def _determine_type(
        self,
        title: str,
        checklist_count: int,
        keyword_score: int,
    ) -> LegendaryType:
        """确定传奇任务类型"""
        title_lower = title.lower()

        # 关键词匹配
        if any(kw in title_lower for kw in ["项目", "计划", "系统"]):
            return LegendaryType.CAMPAIGN
        if any(kw in title_lower for kw in ["研究", "学习", "探索"]):
            return LegendaryType.EXPEDITION
        if any(kw in title_lower for kw in ["维护", "跟进", "监控"]):
            return LegendaryType.ESCORT

        # 基于子任务数量
        if checklist_count >= 8:
            return LegendaryType.SAGA
        elif checklist_count >= 6:
            return LegendaryType.CAMPAIGN

        return LegendaryType.MAIN

    def _estimate_milestones(self, checklist_count: int) -> int:
        """估算里程碑数量"""
        if checklist_count >= 10:
            return 4
        elif checklist_count >= 7:
            return 3
        elif checklist_count >= 5:
            return 2
        return 1

    def get_prefix(self, config: LegendaryConfig) -> str:
        """获取传奇任务前缀

        Args:
            config: 传奇任务配置

        Returns:
            前缀字符串
        """
        # 优先使用自定义前缀
        if config.prefix:
            return config.prefix

        # 获取风格对应的前缀列表
        style_prefixes = LEGENDARY_PREFIXES.get(config.type, {})
        prefixes = style_prefixes.get(self.style, style_prefixes.get("normal", ["【传奇】"]))

        # 返回第一个前缀
        return prefixes[0] if prefixes else "【传奇】"

    def apply_prefix(
        self,
        title: str,
        config: LegendaryConfig,
    ) -> str:
        """为任务标题添加传奇前缀

        Args:
            title: 原标题
            config: 传奇配置

        Returns:
            带前缀的标题
        """
        prefix = self.get_prefix(config)

        # 如果已有前缀，先移除
        for type_prefixes in LEGENDARY_PREFIXES.values():
            for style_prefixes in type_prefixes.values():
                for p in style_prefixes:
                    if title.startswith(p):
                        title = title[len(p):].strip()
                        break

        # 如果是系列任务，添加序号
        if config.series_name and config.series_index:
            return f"{prefix}{config.series_name} · 第{config.series_index}章: {title}"

        return f"{prefix}{title}"


class QuestChain(BaseModel):
    """任务链

    管理同一系列的多个任务。
    """

    name: str = Field(..., description="任务链名称")
    description: Optional[str] = Field(None, description="任务链描述")
    tasks: List[str] = Field(default_factory=list, description="任务 ID 列表（按顺序）")
    current_index: int = Field(0, description="当前任务索引")
    style: str = Field("normal", description="风格")

    def add_task(self, task_id: str) -> None:
        """添加任务到链末尾"""
        if task_id not in self.tasks:
            self.tasks.append(task_id)

    def remove_task(self, task_id: str) -> bool:
        """从链中移除任务"""
        if task_id in self.tasks:
            self.tasks.remove(task_id)
            return True
        return False

    def get_progress(self) -> Tuple[int, int]:
        """获取进度

        Returns:
            (已完成数, 总数)
        """
        return self.current_index, len(self.tasks)

    def get_next_task(self) -> Optional[str]:
        """获取下一个任务 ID"""
        if self.current_index < len(self.tasks):
            return self.tasks[self.current_index]
        return None

    def advance(self) -> Optional[str]:
        """推进到下一个任务

        Returns:
            下一个任务 ID，如果已全部完成则返回 None
        """
        if self.current_index < len(self.tasks) - 1:
            self.current_index += 1
            return self.tasks[self.current_index]
        return None

    def is_completed(self) -> bool:
        """检查是否已全部完成"""
        return self.current_index >= len(self.tasks)

    def render_progress_bar(self) -> str:
        """渲染进度条"""
        total = len(self.tasks)
        completed = self.current_index

        if total == 0:
            return "[dim]空任务链[/]"

        bar_length = min(total, 20)
        filled = int(bar_length * completed / total)

        bar = "█" * filled + "░" * (bar_length - filled)
        return f"[cyan][{bar}][/cyan] {completed}/{total}"

    def render_chain_title(self, index: int) -> str:
        """渲染系列任务标题

        Args:
            index: 任务在系列中的序号（从1开始）

        Returns:
            格式化的标题
        """
        # 罗马数字映射
        roman_numerals = {
            1: "I", 2: "II", 3: "III", 4: "IV", 5: "V",
            6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X",
        }
        numeral = roman_numerals.get(index, str(index))
        return f"{self.name} {numeral}"


class QuestChainManager:
    """任务链管理器

    管理所有任务链，支持创建、查询、更新操作。
    V2 阶段四：支持持久化存储。
    """

    def __init__(self):
        """初始化管理器"""
        self._chains: Dict[str, QuestChain] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """确保数据已从文件加载"""
        if not self._loaded:
            self._load_from_file()
            self._loaded = True

    def _ensure_dir_exists(self) -> None:
        """确保存储目录存在"""
        CHAINS_DIR.mkdir(parents=True, exist_ok=True)

    def _load_from_file(self) -> None:
        """从文件加载任务链数据"""
        try:
            if CHAINS_FILE.exists():
                with open(CHAINS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for chain_data in data.get("chains", []):
                        chain = QuestChain.model_validate(chain_data)
                        self._chains[chain.name] = chain
                logger.info(f"Loaded {len(self._chains)} chains from {CHAINS_FILE}")
        except Exception as e:
            logger.warning(f"Failed to load chains from file: {e}")
            # 加载失败时使用空字典
            self._chains = {}

    def _save_to_file(self) -> None:
        """保存任务链数据到文件"""
        try:
            self._ensure_dir_exists()
            data = {
                "chains": [chain.model_dump() for chain in self._chains.values()],
                "version": 1,
            }
            with open(CHAINS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved {len(self._chains)} chains to {CHAINS_FILE}")
        except Exception as e:
            logger.error(f"Failed to save chains to file: {e}")

    def create_chain(
        self,
        name: str,
        description: Optional[str] = None,
        style: str = "normal",
    ) -> QuestChain:
        """创建新的任务链

        Args:
            name: 任务链名称
            description: 描述
            style: 风格

        Returns:
            创建的任务链
        """
        self._ensure_loaded()
        chain = QuestChain(
            name=name,
            description=description,
            style=style,
        )
        self._chains[name] = chain
        self._save_to_file()
        logger.info(f"Created quest chain: {name}")
        return chain

    def get_chain(self, name: str) -> Optional[QuestChain]:
        """获取任务链"""
        self._ensure_loaded()
        return self._chains.get(name)

    def add_task_to_chain(
        self,
        chain_name: str,
        task_id: str,
    ) -> bool:
        """将任务添加到任务链

        Args:
            chain_name: 任务链名称
            task_id: 任务 ID

        Returns:
            是否成功
        """
        self._ensure_loaded()
        chain = self._chains.get(chain_name)
        if chain:
            chain.add_task(task_id)
            self._save_to_file()
            return True
        return False

    def find_chain_by_task(self, task_id: str) -> Optional[QuestChain]:
        """查找包含指定任务的链

        Args:
            task_id: 任务 ID

        Returns:
            包含该任务的任务链
        """
        self._ensure_loaded()
        for chain in self._chains.values():
            if task_id in chain.tasks:
                return chain
        return None

    def get_all_chains(self) -> List[QuestChain]:
        """获取所有任务链"""
        self._ensure_loaded()
        return list(self._chains.values())

    def delete_chain(self, name: str) -> bool:
        """删除任务链"""
        self._ensure_loaded()
        if name in self._chains:
            del self._chains[name]
            self._save_to_file()
            return True
        return False

    def update_chain(self, chain: QuestChain) -> None:
        """更新任务链（用于推进进度后保存）"""
        self._ensure_loaded()
        if chain.name in self._chains:
            self._chains[chain.name] = chain
            self._save_to_file()

    def reload(self) -> None:
        """重新从文件加载（用于手动刷新）"""
        self._chains.clear()
        self._loaded = False
        self._ensure_loaded()


# 全局任务链管理器实例
_chain_manager: Optional[QuestChainManager] = None


def get_chain_manager() -> QuestChainManager:
    """获取全局任务链管理器"""
    global _chain_manager
    if _chain_manager is None:
        _chain_manager = QuestChainManager()
    return _chain_manager
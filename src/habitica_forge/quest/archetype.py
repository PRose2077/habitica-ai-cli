"""任务原型定义

任务原型是 V2 的核心抽象之一，用于：
- 为任务建立有限的语义分类
- 让 AI 先判断任务原型，再基于原型生成更稳定的游戏化命名
- 为不同原型指定默认动词、名词、语气与奖励倾向

原型列表：
- CLEANUP (清理): 清洁、整理、删除、清理
- REPAIR (修复): 修理、修复、解决、修正
- EXPLORE (探索): 调研、探索、搜索、发现
- CRAFT (制作): 创建、编写、制作、设计
- COMMUNICATE (沟通): 联系、回复、沟通、协调
- LEARN (学习): 学习、研究、阅读、练习
- BATTLE (战斗): 对抗、克服、挑战、解决难题
- SUPPLY (补给): 购买、准备、采购、补充
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from habitica_forge.utils.logger import get_logger

logger = get_logger(__name__)


class QuestArchetype(str, Enum):
    """任务原型枚举

    每个原型代表一类语义相似的任务。
    """

    CLEANUP = "cleanup"      # 清理: 清洁、整理、删除
    REPAIR = "repair"        # 修复: 修理、修正、解决
    EXPLORE = "explore"      # 探索: 调研、搜索、发现
    CRAFT = "craft"         # 制作: 创建、编写、设计
    COMMUNICATE = "communicate"  # 沟通: 联系、回复、协调
    LEARN = "learn"         # 学习: 研究、阅读、练习
    BATTLE = "battle"       # 战斗: 对抗、挑战、解决难题
    SUPPLY = "supply"       # 补给: 购买、准备、补充

    @classmethod
    def from_string(cls, value: str) -> Optional["QuestArchetype"]:
        """从字符串解析原型

        Args:
            value: 原型字符串

        Returns:
            对应的枚举值，无效时返回 None
        """
        try:
            return cls(value.lower())
        except ValueError:
            return None

    def get_display_name(self) -> str:
        """获取中文显示名称"""
        names = {
            QuestArchetype.CLEANUP: "清理",
            QuestArchetype.REPAIR: "修复",
            QuestArchetype.EXPLORE: "探索",
            QuestArchetype.CRAFT: "制作",
            QuestArchetype.COMMUNICATE: "沟通",
            QuestArchetype.LEARN: "学习",
            QuestArchetype.BATTLE: "战斗",
            QuestArchetype.SUPPLY: "补给",
        }
        return names.get(self, "未知")


class ArchetypeKeywords(BaseModel):
    """原型关键词配置"""

    verbs: List[str] = Field(default_factory=list, description="动作动词")
    nouns: List[str] = Field(default_factory=list, description="相关名词")
    triggers: List[str] = Field(default_factory=list, description="触发词（用于识别原型）")


class ArchetypeConfig(BaseModel):
    """原型配置

    定义每个原型的游戏化规则。
    """

    name: str = Field(..., description="原型名称")
    display_name: str = Field(..., description="显示名称")
    description: str = Field(..., description="原型描述")

    # 关键词
    keywords: ArchetypeKeywords = Field(
        default_factory=ArchetypeKeywords,
        description="关键词配置"
    )

    # 游戏化配置
    fantasy_verbs: List[str] = Field(default_factory=list, description="奇幻风格动词")
    fantasy_nouns: List[str] = Field(default_factory=list, description="奇幻风格名词")
    cyberpunk_verbs: List[str] = Field(default_factory=list, description="赛博风格动词")
    cyberpunk_nouns: List[str] = Field(default_factory=list, description="赛博风格名词")
    wuxia_verbs: List[str] = Field(default_factory=list, description="武侠风格动词")
    wuxia_nouns: List[str] = Field(default_factory=list, description="武侠风格名词")

    # 奖励倾向
    reward_tendency: str = Field(
        default="balanced",
        description="奖励倾向: balanced(平衡), combat(战斗), exploration(探索), crafting(制作)"
    )

    # 语气
    tone: str = Field(
        default="neutral",
        description="语气: neutral(中性), urgent(紧迫), relaxed(轻松), epic(史诗)"
    )


# 默认原型配置
DEFAULT_ARCHETYPE_CONFIGS: Dict[QuestArchetype, ArchetypeConfig] = {
    QuestArchetype.CLEANUP: ArchetypeConfig(
        name="cleanup",
        display_name="清理",
        description="清洁、整理、删除、清理类任务",
        keywords=ArchetypeKeywords(
            verbs=["清洁", "整理", "清理", "删除", "清除", "打扫", "收拾", "丢弃"],
            nouns=["垃圾", "杂物", "灰尘", "文件", "数据"],
            triggers=["打扫", "整理", "清理", "删除", "收拾", "清洁", "清理干净", "扔掉"]
        ),
        fantasy_verbs=["净化", "驱除", "清扫", "洗礼", "驱逐"],
        fantasy_nouns=["污秽", "诅咒", "阴影", "杂物"],
        cyberpunk_verbs=["擦除", "清理", "删除", "格式化", "清洗"],
        cyberpunk_nouns=["垃圾数据", "冗余", "痕迹", "缓存"],
        wuxia_verbs=["涤荡", "扫除", "清理", "斩断"],
        wuxia_nouns=["尘埃", "杂念", "俗务", "障碍"],
        reward_tendency="balanced",
        tone="relaxed"
    ),

    QuestArchetype.REPAIR: ArchetypeConfig(
        name="repair",
        display_name="修复",
        description="修理、修复、解决、修正类任务",
        keywords=ArchetypeKeywords(
            verbs=["修理", "修复", "修正", "解决", "修复", "纠正", "弥补"],
            nouns=["问题", "错误", "故障", "缺陷", "漏洞"],
            triggers=["修理", "修复", "修正", "解决", "fix", "bug", "修复bug", "纠错"]
        ),
        fantasy_verbs=["修复", "治愈", "复原", "重建", "加固"],
        fantasy_nouns=["创伤", "裂痕", "损坏", "破损"],
        cyberpunk_verbs=["调试", "修补", "优化", "重构", "修复"],
        cyberpunk_nouns=["漏洞", "故障", "缺陷", "错误"],
        wuxia_verbs=["疗伤", "修补", "调理", "修复"],
        wuxia_nouns=["内伤", "经脉", "破损", "损耗"],
        reward_tendency="balanced",
        tone="neutral"
    ),

    QuestArchetype.EXPLORE: ArchetypeConfig(
        name="explore",
        display_name="探索",
        description="调研、探索、搜索、发现类任务",
        keywords=ArchetypeKeywords(
            verbs=["调研", "探索", "搜索", "发现", "研究", "调查", "寻找"],
            nouns=["信息", "资料", "数据", "知识"],
            triggers=["调研", "探索", "搜索", "查找", "研究", "调查", "寻找", "了解"]
        ),
        fantasy_verbs=["探索", "搜寻", "寻觅", "侦察", "探测"],
        fantasy_nouns=["遗迹", "宝藏", "秘境", "未知"],
        cyberpunk_verbs=["扫描", "检索", "挖掘", "解析", "探索"],
        cyberpunk_nouns=["数据", "信号", "网络", "暗网"],
        wuxia_verbs=["探寻", "搜寻", "探访", "踏访"],
        wuxia_nouns=["秘籍", "遗迹", "传说", "线索"],
        reward_tendency="exploration",
        tone="relaxed"
    ),

    QuestArchetype.CRAFT: ArchetypeConfig(
        name="craft",
        display_name="制作",
        description="创建、编写、制作、设计类任务",
        keywords=ArchetypeKeywords(
            verbs=["创建", "编写", "制作", "设计", "开发", "构建", "搭建", "写作"],
            nouns=["项目", "代码", "文档", "产品", "内容"],
            triggers=["创建", "编写", "开发", "设计", "制作", "写", "开发项目", "新建"]
        ),
        fantasy_verbs=["锻造", "铸造", "创造", "雕琢", "编织"],
        fantasy_nouns=["神器", "魔法", "卷轴", "物品"],
        cyberpunk_verbs=["编译", "构建", "创建", "生成", "开发"],
        cyberpunk_nouns=["程序", "系统", "模块", "组件"],
        wuxia_verbs=["锻造", "炼制", "创造", "修炼"],
        wuxia_nouns=["神兵", "丹药", "功法", "秘籍"],
        reward_tendency="crafting",
        tone="neutral"
    ),

    QuestArchetype.COMMUNICATE: ArchetypeConfig(
        name="communicate",
        display_name="沟通",
        description="联系、回复、沟通、协调类任务",
        keywords=ArchetypeKeywords(
            verbs=["联系", "回复", "沟通", "协调", "通知", "发送", "回复", "讨论"],
            nouns=["邮件", "消息", "会议", "沟通", "协调"],
            triggers=["发邮件", "回复", "联系", "沟通", "通知", "开会", "讨论", "发消息"]
        ),
        fantasy_verbs=["传讯", "联络", "召见", "会晤", "书信"],
        fantasy_nouns=["信使", "公会", "同伴", "盟友"],
        cyberpunk_verbs=["连接", "发送", "同步", "通信", "联络"],
        cyberpunk_nouns=["信号", "频道", "网络", "终端"],
        wuxia_verbs=["传书", "联络", "拜访", "约见"],
        wuxia_nouns=["江湖", "同道", "门派", "侠客"],
        reward_tendency="balanced",
        tone="relaxed"
    ),

    QuestArchetype.LEARN: ArchetypeConfig(
        name="learn",
        display_name="学习",
        description="学习、研究、阅读、练习类任务",
        keywords=ArchetypeKeywords(
            verbs=["学习", "研究", "阅读", "练习", "培训", "进修", "掌握"],
            nouns=["知识", "技能", "课程", "教程", "方法"],
            triggers=["学习", "研究", "阅读", "练习", "培训", "教程", "课程"]
        ),
        fantasy_verbs=["研习", "修炼", "参悟", "领悟", "习得"],
        fantasy_nouns=["魔法", "咒语", "技能", "智慧"],
        cyberpunk_verbs=["学习", "下载", "加载", "编译", "训练"],
        cyberpunk_nouns=["技能", "知识库", "模块", "程序"],
        wuxia_verbs=["修炼", "参悟", "研习", "领悟"],
        wuxia_nouns=["内功", "心法", "招式", "武学"],
        reward_tendency="crafting",
        tone="relaxed"
    ),

    QuestArchetype.BATTLE: ArchetypeConfig(
        name="battle",
        display_name="战斗",
        description="对抗、克服、挑战、解决难题类任务",
        keywords=ArchetypeKeywords(
            verbs=["对抗", "克服", "挑战", "解决", "战胜", "击败", "攻坚"],
            nouns=["困难", "挑战", "难题", "对手", "障碍"],
            triggers=["挑战", "战胜", "克服", "对抗", "解决难题", "攻坚", "突破"]
        ),
        fantasy_verbs=["讨伐", "征服", "战胜", "击退", "斩杀"],
        fantasy_nouns=["怪物", "敌人", "魔兽", "魔王"],
        cyberpunk_verbs=["对抗", "击破", "攻陷", "突破", "入侵"],
        cyberpunk_nouns=["防火墙", "系统", "敌人", "对手"],
        wuxia_verbs=["对决", "击败", "降伏", "征服"],
        wuxia_nouns=["对手", "强敌", "魔头", "妖邪"],
        reward_tendency="combat",
        tone="epic"
    ),

    QuestArchetype.SUPPLY: ArchetypeConfig(
        name="supply",
        display_name="补给",
        description="购买、准备、采购、补充类任务",
        keywords=ArchetypeKeywords(
            verbs=["购买", "准备", "采购", "补充", "储备", "收集", "获取"],
            nouns=["物资", "材料", "资源", "用品", "装备"],
            triggers=["买", "购买", "采购", "准备", "补充", "储备", "收集"]
        ),
        fantasy_verbs=["采购", "收集", "筹备", "补给", "收集"],
        fantasy_nouns=["物资", "药剂", "装备", "补给品"],
        cyberpunk_verbs=["采购", "下载", "获取", "加载", "补充"],
        cyberpunk_nouns=["资源", "数据", "组件", "插件"],
        wuxia_verbs=["筹集", "收集", "准备", "补充"],
        wuxia_nouns=["丹药", "兵器", "盘缠", "物资"],
        reward_tendency="balanced",
        tone="relaxed"
    ),
}


def get_archetype_config(archetype: QuestArchetype) -> ArchetypeConfig:
    """获取原型配置

    Args:
        archetype: 任务原型

    Returns:
        原型配置
    """
    return DEFAULT_ARCHETYPE_CONFIGS.get(archetype)


def detect_archetype_from_text(text: str) -> Optional[QuestArchetype]:
    """从文本中检测任务原型

    基于关键词匹配识别最可能的原型。

    Args:
        text: 任务文本

    Returns:
        检测到的原型，无法识别时返回 None
    """
    text_lower = text.lower()

    best_match: Optional[QuestArchetype] = None
    best_score = 0

    for archetype, config in DEFAULT_ARCHETYPE_CONFIGS.items():
        score = 0

        # 检查触发词
        for trigger in config.keywords.triggers:
            if trigger.lower() in text_lower:
                score += 2

        # 检查动词
        for verb in config.keywords.verbs:
            if verb.lower() in text_lower:
                score += 1

        if score > best_score:
            best_score = score
            best_match = archetype

    return best_match


def get_style_verbs(archetype: QuestArchetype, style: str) -> List[str]:
    """获取特定风格的原型动词

    Args:
        archetype: 任务原型
        style: 风格名称

    Returns:
        该风格下的动词列表
    """
    config = get_archetype_config(archetype)
    if not config:
        return []

    style = style.lower()

    if style == "fantasy":
        return config.fantasy_verbs
    elif style == "cyberpunk":
        return config.cyberpunk_verbs
    elif style == "wuxia":
        return config.wuxia_verbs
    else:
        return config.keywords.verbs


def get_style_nouns(archetype: QuestArchetype, style: str) -> List[str]:
    """获取特定风格的原型名词

    Args:
        archetype: 任务原型
        style: 风格名称

    Returns:
        该风格下的名词列表
    """
    config = get_archetype_config(archetype)
    if not config:
        return []

    style = style.lower()

    if style == "fantasy":
        return config.fantasy_nouns
    elif style == "cyberpunk":
        return config.cyberpunk_nouns
    elif style == "wuxia":
        return config.wuxia_nouns
    else:
        return config.keywords.nouns
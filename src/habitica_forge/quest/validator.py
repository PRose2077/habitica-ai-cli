"""游戏化可读性约束

实现 V2 的游戏化约束规则：
1. 游戏化标题长度上限（默认 50 字符）
2. 每条游戏化标题必须保留一个现实关键词
3. 过度浮夸时自动回退到保守命名

这些约束确保游戏化不会牺牲任务的可执行性。
"""

import re
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from habitica_forge.quest.archetype import QuestArchetype
from habitica_forge.utils.logger import get_logger

logger = get_logger(__name__)

# ============================================
# 约束配置
# ============================================

# 默认最大标题长度
DEFAULT_MAX_TITLE_LENGTH = 50

# 浮夸词汇模式（需要回退的过度游戏化模式）
EXCESSIVE_PATTERNS = [
    # 过度修饰
    r"传说中的.*传说中的",
    r"超级.*超级",
    r"终极.*终极",
    # 不切实际的表述
    r"不可能完成",
    r"无法想象",
    r"超越神",
    # 过于模糊的表述
    r"某种.*某种",
    r"某些.*某些",
]

# 编译正则
EXCESSIVE_REGEX = [re.compile(p) for p in EXCESSIVE_PATTERNS]


class GamificationConstraints(BaseModel):
    """游戏化约束配置"""

    max_title_length: int = Field(
        default=DEFAULT_MAX_TITLE_LENGTH,
        description="最大标题长度"
    )
    require_real_keyword: bool = Field(
        default=True,
        description="是否要求保留现实关键词"
    )
    auto_fallback: bool = Field(
        default=True,
        description="过度浮夸时是否自动回退"
    )
    min_real_keyword_length: int = Field(
        default=2,
        description="现实关键词最小长度"
    )


class ValidationResult(BaseModel):
    """验证结果"""

    is_valid: bool = Field(..., description="是否通过验证")
    quest_title: str = Field(..., description="游戏化标题")
    issues: List[str] = Field(default_factory=list, description="问题列表")
    fallback_used: bool = Field(default=False, description="是否使用了回退")


# ============================================
# 验证器类
# ============================================

class GamificationValidator:
    """游戏化验证器

    确保 AI 生成的游戏化标题满足可读性约束。
    """

    def __init__(self, constraints: Optional[GamificationConstraints] = None):
        """初始化验证器

        Args:
            constraints: 约束配置，默认使用默认配置
        """
        self.constraints = constraints or GamificationConstraints()

    def validate(
        self,
        quest_title: str,
        real_title: str,
        auto_fix: bool = True
    ) -> ValidationResult:
        """验证游戏化标题

        Args:
            quest_title: 游戏化标题
            real_title: 现实标题（用于关键词检查和回退）
            auto_fix: 是否自动修复问题

        Returns:
            验证结果
        """
        issues: List[str] = []

        # 1. 检查长度
        if len(quest_title) > self.constraints.max_title_length:
            issues.append(
                f"标题过长 ({len(quest_title)} > {self.constraints.max_title_length})"
            )

        # 2. 检查是否保留现实关键词
        if self.constraints.require_real_keyword:
            if not self._has_real_keyword(quest_title, real_title):
                issues.append("未保留现实关键词")

        # 3. 检查是否过度浮夸
        if self.constraints.auto_fallback:
            if self._is_excessive(quest_title):
                issues.append("过度游戏化/浮夸")

        # 如果有问题且启用自动修复
        if issues and auto_fix:
            fallback_title = self._generate_fallback(quest_title, real_title, issues)
            return ValidationResult(
                is_valid=False,
                quest_title=fallback_title,
                issues=issues,
                fallback_used=True
            )

        return ValidationResult(
            is_valid=len(issues) == 0,
            quest_title=quest_title,
            issues=issues,
            fallback_used=False
        )

    def _has_real_keyword(self, quest_title: str, real_title: str) -> bool:
        """检查游戏化标题是否包含现实关键词

        Args:
            quest_title: 游戏化标题
            real_title: 现实标题

        Returns:
            是否包含关键词
        """
        # 从现实标题中提取关键词
        keywords = self._extract_keywords(real_title)

        # 检查游戏化标题是否包含任一关键词
        for keyword in keywords:
            if len(keyword) >= self.constraints.min_real_keyword_length:
                if keyword in quest_title:
                    return True

        return False

    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词

        Args:
            text: 文本

        Returns:
            关键词列表
        """
        # 简单分词：按空格和标点分割
        # 去除停用词和标点
        stop_words = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这"}

        # 分词 - 匹配各种分隔符
        words = re.split(
            r"[\s,，。！？、：；""''（）\【\】{}\[\]<>《》]+",
            text,
            flags=re.UNICODE
        )

        # 过滤
        keywords = []
        for word in words:
            word = word.strip()
            if len(word) >= 2 and word not in stop_words:
                keywords.append(word)

        return keywords

    def _is_excessive(self, text: str) -> bool:
        """检查文本是否过度浮夸

        Args:
            text: 待检查文本

        Returns:
            是否过度浮夸
        """
        for pattern in EXCESSIVE_REGEX:
            if pattern.search(text):
                return True

        # 检查特殊符号过多
        special_char_count = len(re.findall(r"[【】\[\]★☆◆◇●○▲△]", text))
        if special_char_count > 4:
            return True

        return False

    def _generate_fallback(
        self,
        quest_title: str,
        real_title: str,
        issues: List[str]
    ) -> str:
        """生成回退标题

        Args:
            quest_title: 原游戏化标题
            real_title: 现实标题
            issues: 问题列表

        Returns:
            回退后的标题
        """
        # 如果标题过长，截断
        if "标题过长" in str(issues):
            if len(real_title) <= self.constraints.max_title_length:
                return real_title
            return quest_title[:self.constraints.max_title_length] + "…"

        # 如果缺少关键词或过度浮夸，使用保守命名
        if "未保留现实关键词" in str(issues) or "过度游戏化" in str(issues):
            # 尝试生成保守的游戏化标题
            return self._conservative_gamify(real_title)

        return quest_title

    def _conservative_gamify(self, real_title: str) -> str:
        """保守的游戏化处理

        在保证可读性的前提下，添加最小化的游戏化元素。

        Args:
            real_title: 现实标题

        Returns:
            保守游戏化的标题
        """
        # 如果标题本身已经合适，直接返回
        if len(real_title) <= self.constraints.max_title_length:
            return real_title

        # 截断处理
        return real_title[:self.constraints.max_title_length - 1] + "…"


# ============================================
# 便捷函数
# ============================================

def validate_gamified_title(
    quest_title: str,
    real_title: str,
    max_length: int = DEFAULT_MAX_TITLE_LENGTH
) -> Tuple[str, bool]:
    """验证并修复游戏化标题

    Args:
        quest_title: 游戏化标题
        real_title: 现实标题
        max_length: 最大长度

    Returns:
        (处理后的标题, 是否使用了回退)
    """
    constraints = GamificationConstraints(max_title_length=max_length)
    validator = GamificationValidator(constraints)
    result = validator.validate(quest_title, real_title)
    return result.quest_title, result.fallback_used


def ensure_real_keyword(
    quest_title: str,
    real_title: str
) -> str:
    """确保游戏化标题包含现实关键词

    如果不包含，返回一个包含关键词的版本。

    Args:
        quest_title: 游戏化标题
        real_title: 现实标题

    Returns:
        包含关键词的标题
    """
    validator = GamificationValidator()
    keywords = validator._extract_keywords(real_title)

    # 找到最长的关键词
    if keywords:
        main_keyword = max(keywords, key=len)
        if main_keyword not in quest_title:
            # 将关键词添加到标题中
            return f"{quest_title} ({main_keyword})"

    return quest_title


def truncate_title(
    title: str,
    max_length: int = DEFAULT_MAX_TITLE_LENGTH
) -> str:
    """截断过长的标题

    Args:
        title: 标题
        max_length: 最大长度

    Returns:
        截断后的标题
    """
    if len(title) <= max_length:
        return title

    # 尝试在合适的断点截断
    # 优先在标点或空格处截断
    truncate_at = max_length - 1

    # 查找最近的断点
    for i in range(truncate_at, max(truncate_at - 10, 0), -1):
        if title[i] in "，。！？、：；,!?;: ":
            truncate_at = i
            break

    return title[:truncate_at] + "…"


# 全局验证器实例
_default_validator: Optional[GamificationValidator] = None


def get_default_validator() -> GamificationValidator:
    """获取默认验证器实例"""
    global _default_validator
    if _default_validator is None:
        _default_validator = GamificationValidator()
    return _default_validator
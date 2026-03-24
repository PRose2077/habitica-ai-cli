"""悬赏掉落算法判定器

根据 PRD 定义的公式：
    Drop_Score = (难度权重 × 类型权重) + RNG(随机数)

触发条件：Drop_Score >= TITLE_THRESHOLD 则触发称号生成
"""

import os
import random
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Literal, Optional

from habitica_forge.core.config import settings
from habitica_forge.utils.logger import get_logger

logger = get_logger(__name__)

# 任务类型
TaskType = Literal["todo", "daily", "habit", "reward"]

# 优先级到难度的映射
PRIORITY_TO_DIFFICULTY = {
    0.1: 1.0,   # trivial
    1.0: 2.0,   # easy
    1.5: 3.0,   # medium
    2.0: 4.0,   # hard
}

# 类型权重系数（可以独立调整）
TYPE_WEIGHTS = {
    "todo": 1.0,
    "daily": 0.8,  # Daily 任务更容易掉落
    "habit": 0.5,
    "reward": 0.0,  # 奖励不掉落
}


@dataclass
class DropResult:
    """掉落判定结果"""

    dropped: bool
    drop_score: float
    difficulty: float
    type_weight: float
    rng_value: float
    threshold: float


def calculate_drop_score(
    priority: float,
    task_type: TaskType,
    streak: int = 0,
) -> DropResult:
    """
    计算掉落分数

    公式: Drop_Score = (难度权重 × 类型权重) + RNG

    Args:
        priority: 任务优先级 (0.1, 1.0, 1.5, 2.0)
        task_type: 任务类型 (todo, daily, habit, reward)
        streak: 连击天数（仅 Daily 任务有效）

    Returns:
        DropResult: 掉落判定结果
    """
    # 获取难度权重
    difficulty = PRIORITY_TO_DIFFICULTY.get(priority, 2.0)

    # 获取类型权重
    type_weight = TYPE_WEIGHTS.get(task_type, 1.0)

    # 计算基础分数: (难度权重 × 类型权重)
    base_score = difficulty * type_weight

    # Daily 任务加成连击奖励
    streak_bonus = 0.0
    if task_type == "daily" and streak > 0:
        streak_bonus = streak * settings.daily_streak_bonus

    # RNG 随机值 (0-5)
    rng_value = random.uniform(0, 5)

    # 最终分数: (难度权重 × 类型权重) + RNG + 连击奖励
    drop_score = base_score + rng_value + streak_bonus

    # 获取阈值
    threshold = settings.title_threshold

    # 判定是否掉落
    dropped = drop_score >= threshold

    result = DropResult(
        dropped=dropped,
        drop_score=round(drop_score, 2),
        difficulty=difficulty,
        type_weight=type_weight,
        rng_value=round(rng_value, 2),
        threshold=threshold,
    )

    if dropped:
        logger.info(
            f"Title drop triggered! Score: {drop_score:.2f} >= {threshold} "
            f"(difficulty={difficulty}, type_weight={type_weight}, rng={rng_value:.2f})"
        )
    else:
        logger.debug(
            f"No drop. Score: {drop_score:.2f} < {threshold}"
        )

    return result


def check_bounty_drop(
    priority: float = 1.0,
    task_type: TaskType = "todo",
    streak: int = 0,
) -> bool:
    """
    检查是否触发悬赏掉落

    这是一个便捷函数，只返回是否掉落的结果。

    Args:
        priority: 任务优先级
        task_type: 任务类型
        streak: 连击天数

    Returns:
        bool: 是否触发掉落
    """
    # Reward 类型不掉落
    if task_type == "reward":
        return False

    result = calculate_drop_score(priority, task_type, streak)
    return result.dropped


# ============================================
# 称号相关常量和工具函数
# ============================================

# 称号标签前缀
WALL_TAG_PREFIX = "【WALL"
WALL_TAG_PENDING_PREFIX = "【WALL待激活】"
WALL_TAG_ACTIVE_PREFIX = "【WALL】"
WALL_TAG_EQUIPPED_SUFFIX = "No.1"


def is_wall_tag(tag_name: str) -> bool:
    """检查标签是否为称号标签"""
    return tag_name.startswith(WALL_TAG_PREFIX)


def is_pending_wall_tag(tag_name: str) -> bool:
    """检查标签是否为待激活称号"""
    return tag_name.startswith(WALL_TAG_PENDING_PREFIX)


def is_active_wall_tag(tag_name: str) -> bool:
    """检查标签是否为已激活称号"""
    return tag_name.startswith(WALL_TAG_ACTIVE_PREFIX)


def is_equipped_wall_tag(tag_name: str) -> bool:
    """检查标签是否为当前佩戴的称号"""
    return "【WALL No.1】" in tag_name


def extract_title_name(tag_name: str) -> str:
    """
    从标签名中提取称号名称

    Args:
        tag_name: 标签名称，如 "【WALL待激活】星尘征服者" 或 "【WALL】星尘征服者"
                  或 "【WALL No.1】星尘征服者"

    Returns:
        称号名称（不含 No.1 后缀）
    """
    if is_pending_wall_tag(tag_name):
        return tag_name[len(WALL_TAG_PENDING_PREFIX):]
    elif is_equipped_wall_tag(tag_name):
        # 格式是 "【WALL No.1】称号名"
        prefix = "【WALL No.1】"
        return tag_name[len(prefix):]
    elif is_active_wall_tag(tag_name):
        # 格式是 "【WALL】称号名"
        title = tag_name[len(WALL_TAG_ACTIVE_PREFIX):]
        # 去掉可能存在的 No.1 后缀（兼容旧格式）
        if title.endswith(f" {WALL_TAG_EQUIPPED_SUFFIX}"):
            title = title[: -len(f" {WALL_TAG_EQUIPPED_SUFFIX}")]
        return title
    return tag_name


def make_pending_tag_name(title: str) -> str:
    """创建待激活标签名"""
    return f"{WALL_TAG_PENDING_PREFIX}{title}"


def make_active_tag_name(title: str, equipped: bool = False) -> str:
    """
    创建激活标签名

    Args:
        title: 称号名称
        equipped: 是否为佩戴状态

    Returns:
        标签名称：
        - 佩戴中: "【WALL No.1】称号名"
        - 未佩戴: "【WALL】称号名"
    """
    if equipped:
        return f"【WALL No.1】{title}"
    return f"{WALL_TAG_ACTIVE_PREFIX}{title}"


@dataclass
class WallTag:
    """称号标签数据"""

    id: str
    name: str
    title: str
    status: Literal["pending", "active", "equipped"]

    @classmethod
    def from_tag(cls, tag_id: str, tag_name: str) -> Optional["WallTag"]:
        """从标签创建 WallTag"""
        if not is_wall_tag(tag_name):
            return None

        if is_pending_wall_tag(tag_name):
            status = "pending"
        elif is_equipped_wall_tag(tag_name):
            status = "equipped"
        else:
            status = "active"

        title = extract_title_name(tag_name)

        return cls(
            id=tag_id,
            name=tag_name,
            title=title,
            status=status,
        )


def parse_wall_tags(tags: List[dict]) -> List[WallTag]:
    """
    解析标签列表，提取所有称号标签

    Args:
        tags: 标签列表，每项包含 id 和 name

    Returns:
        称号标签列表
    """
    wall_tags = []
    for tag in tags:
        wall_tag = WallTag.from_tag(
            tag.get("id", ""),
            tag.get("name", ""),
        )
        if wall_tag:
            wall_tags.append(wall_tag)

    return wall_tags


# ============================================
# 后台进程启动函数 (Fire-and-Forget)
# ============================================


def spawn_title_generator(
    task_id: str,
    task_text: str,
    style: Optional[str] = None,
) -> bool:
    """
    在后台启动称号生成脚本

    这是 Fire-and-Forget 模式：主进程立即返回，后台进程独立运行。

    Args:
        task_id: 任务 ID
        task_text: 任务内容
        style: 游戏化风格

    Returns:
        是否成功启动后台进程
    """
    try:
        # 构建命令
        python_executable = sys.executable

        # 使用 -m 方式运行模块
        cmd = [
            python_executable,
            "-m",
            "habitica_forge.scripts.title_generator",
            task_id,
            task_text,
        ]

        if style:
            cmd.extend(["--style", style])

        # 在后台启动进程
        # 使用 DETACHED_PROCESS 和 CREATE_NO_WINDOW (Windows)
        # 或使用 start_new_session (Unix)
        kwargs = {}

        if sys.platform == "win32":
            # Windows: 完全脱离父进程
            kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS |
                subprocess.CREATE_NO_WINDOW |
                subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            # Unix: 创建新的会话
            kwargs["start_new_session"] = True

        # 重定向输出到 /dev/null 或 NUL
        with open(os.devnull, "w") as devnull:
            subprocess.Popen(
                cmd,
                stdout=devnull,
                stderr=devnull,
                stdin=subprocess.DEVNULL,
                **kwargs,
            )

        logger.info(
            f"Spawned background title generator for task {task_id[:8]}"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to spawn title generator: {e}")
        return False


def trigger_bounty_drop(
    task_id: str,
    task_text: str,
    priority: float = 1.0,
    task_type: TaskType = "todo",
    streak: int = 0,
    style: Optional[str] = None,
) -> bool:
    """
    检查并触发悬赏掉落

    如果触发掉落，在后台启动称号生成脚本。

    Args:
        task_id: 任务 ID
        task_text: 任务内容
        priority: 任务优先级
        task_type: 任务类型
        streak: 连击天数
        style: 游戏化风格

    Returns:
        是否触发了掉落
    """
    # 检查是否触发掉落
    result = calculate_drop_score(priority, task_type, streak)

    if result.dropped:
        # 在后台启动称号生成
        spawn_title_generator(task_id, task_text, style)
        logger.info(
            f"Bounty drop triggered! Score: {result.drop_score} >= {result.threshold}"
        )
        return True

    return False


# ============================================
# 任务链完成奖励 (V2 阶段四)
# ============================================

# 任务链完成奖励系数
CHAIN_COMPLETION_BONUS = {
    2: 1.5,   # 2个任务的链，掉落概率 +50%
    3: 2.0,   # 3个任务的链，掉落概率 +100%
    4: 2.5,   # 4个任务的链，掉落概率 +150%
    5: 3.0,   # 5个任务的链，掉落概率 +200%
}

# 任务链完成额外奖励阈值
CHAIN_TITLE_THRESHOLD_BONUS = -2.0  # 降低阈值，提高掉落概率


def calculate_chain_completion_bonus(
    chain_length: int,
    chain_name: Optional[str] = None,
) -> dict:
    """
    计算任务链完成的奖励加成

    V2 阶段四新增：
    - 根据任务链长度计算奖励加成
    - 返回奖励详情用于展示

    Args:
        chain_length: 任务链长度（任务数量）
        chain_name: 任务链名称（可选，用于展示）

    Returns:
        dict: 包含奖励详情的字典
            - bonus_multiplier: 掉落概率加成系数
            - threshold_reduction: 阈值降低值
            - guaranteed_drop: 是否保证掉落
            - message: 奖励信息
    """
    # 获取基础加成
    bonus_multiplier = CHAIN_COMPLETION_BONUS.get(chain_length, 3.0)

    # 超过 5 个任务的链，保证掉落
    guaranteed_drop = chain_length >= 5

    # 计算阈值降低
    threshold_reduction = CHAIN_TITLE_THRESHOLD_BONUS

    # 构建奖励信息
    if guaranteed_drop:
        message = f"任务链「{chain_name or '未命名'}」完成！获得稀有称号！"
    elif bonus_multiplier >= 2.0:
        message = f"任务链「{chain_name or '未命名'}」完成！称号掉落概率大幅提升！"
    else:
        message = f"任务链「{chain_name or '未命名'}」完成！称号掉落概率提升！"

    return {
        "bonus_multiplier": bonus_multiplier,
        "threshold_reduction": threshold_reduction,
        "guaranteed_drop": guaranteed_drop,
        "message": message,
        "chain_length": chain_length,
    }


def trigger_chain_completion_reward(
    task_id: str,
    task_text: str,
    chain_length: int,
    chain_name: Optional[str] = None,
    style: Optional[str] = None,
    priority: float = 1.5,
) -> bool:
    """
    触发任务链完成奖励

    V2 阶段四新增：
    - 任务链完成时调用此函数
    - 给予更高概率的称号掉落
    - 长任务链可能保证掉落

    Args:
        task_id: 任务 ID
        task_text: 任务内容
        chain_length: 任务链长度
        chain_name: 任务链名称
        style: 游戏化风格
        priority: 任务优先级

    Returns:
        是否触发了掉落
    """
    # 计算奖励
    bonus = calculate_chain_completion_bonus(chain_length, chain_name)

    # 如果保证掉落
    if bonus["guaranteed_drop"]:
        spawn_title_generator(task_id, task_text, style)
        logger.info(f"Chain completion guaranteed drop! Chain: {chain_name}")
        return True

    # 计算调整后的分数
    result = calculate_drop_score(priority, "todo", 0)

    # 应用加成
    adjusted_score = result.drop_score * bonus["bonus_multiplier"]
    adjusted_threshold = result.threshold + bonus["threshold_reduction"]

    if adjusted_score >= adjusted_threshold:
        spawn_title_generator(task_id, task_text, style)
        logger.info(
            f"Chain completion drop triggered! "
            f"Adjusted score: {adjusted_score:.2f} >= {adjusted_threshold:.2f}"
        )
        return True

    return False
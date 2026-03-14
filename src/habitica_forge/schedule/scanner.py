"""深渊腐烂扫描器

独立可执行脚本，用于扫描过期任务并进行批量黑化处理。

功能：
1. 拉取 todos，对比 updatedAt 提取过期任务
2. 剔除已标记最高腐烂等级（CORRUPTED_LVL: 3）的任务
3. 将任务打包发送给 LLM 进行批量黑化
4. 使用 asyncio.Semaphore 限制并发更新

使用方式:
    python -m habitica_forge.schedule.scanner [--force]
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from habitica_forge.ai.llm_client import LLMClient
from habitica_forge.clients.habitica import HabiticaClient
from habitica_forge.core.config import settings
from habitica_forge.utils.logger import get_logger, init_logging

logger = get_logger(__name__)

# 腐烂标记格式
CORRUPTION_MARKER = "<!-- CORRUPTED_LVL: {} -->"
MAX_CORRUPTION_LEVEL = 3

# 扫描时间记录文件
SCAN_TIME_FILE = Path.home() / ".config" / "habitica-forge" / "last_scan_time.json"

# 过期阈值（天）
STALE_THRESHOLD_DAYS = 3


def get_scan_time_file() -> Path:
    """获取扫描时间记录文件路径"""
    SCAN_TIME_FILE.parent.mkdir(parents=True, exist_ok=True)
    return SCAN_TIME_FILE


def get_last_scan_time() -> Optional[datetime]:
    """获取上次扫描时间"""
    try:
        file_path = get_scan_time_file()
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return datetime.fromisoformat(data.get("last_scan_time"))
    except Exception as e:
        logger.warning(f"Failed to read last scan time: {e}")
    return None


def set_last_scan_time() -> None:
    """设置当前扫描时间"""
    try:
        file_path = get_scan_time_file()
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(
                {"last_scan_time": datetime.now(timezone.utc).isoformat()},
                f,
                ensure_ascii=False,
            )
    except Exception as e:
        logger.warning(f"Failed to write last scan time: {e}")


def should_scan(force: bool = False) -> bool:
    """
    检查是否应该执行扫描

    Args:
        force: 是否强制扫描

    Returns:
        是否应该执行扫描
    """
    if force:
        return True

    last_scan = get_last_scan_time()
    if last_scan is None:
        return True

    interval_hours = settings.scan_interval_hours
    next_scan = last_scan + timedelta(hours=interval_hours)

    return datetime.now(timezone.utc) >= next_scan


def extract_corruption_level(notes: Optional[str]) -> int:
    """
    从任务备注中提取腐烂等级

    Args:
        notes: 任务备注

    Returns:
        腐烂等级（0 表示未腐烂）
    """
    if not notes:
        return 0

    import re

    pattern = r"<!-- CORRUPTED_LVL: (\d+) -->"
    match = re.search(pattern, notes)
    if match:
        return int(match.group(1))
    return 0


def add_corruption_marker(notes: Optional[str], level: int) -> str:
    """
    添加腐烂标记到任务备注

    Args:
        notes: 原任务备注
        level: 腐烂等级

    Returns:
        添加标记后的备注
    """
    import re

    marker = CORRUPTION_MARKER.format(level)

    if not notes:
        return marker

    # 移除旧的标记
    pattern = r"<!-- CORRUPTED_LVL: \d+ -->\s*"
    cleaned = re.sub(pattern, "", notes)

    return f"{cleaned}\n{marker}"


async def fetch_stale_tasks(client: HabiticaClient) -> List[Dict[str, Any]]:
    """
    获取过期任务

    Args:
        client: Habitica 客户端

    Returns:
        过期任务列表
    """
    # 获取所有 todos
    tasks = await client.get_tasks("todos")

    # 过滤未完成的任务
    pending_tasks = [t for t in tasks if not t.completed]

    # 计算过期阈值
    stale_threshold = datetime.now(timezone.utc) - timedelta(days=STALE_THRESHOLD_DAYS)

    stale_tasks = []
    for task in pending_tasks:
        # 检查 updatedAt
        if task.updatedAt:
            updated_at = task.updatedAt
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)

            # 检查是否过期
            if updated_at < stale_threshold:
                # 检查腐烂等级
                corruption_level = extract_corruption_level(task.notes)

                # 剔除已达最高腐烂等级的任务
                if corruption_level < MAX_CORRUPTION_LEVEL:
                    stale_tasks.append(
                        {
                            "id": task.id,
                            "text": task.text,
                            "notes": task.notes,
                            "corruption_level": corruption_level,
                            "updated_at": updated_at,
                        }
                    )

    logger.info(f"Found {len(stale_tasks)} stale tasks")
    return stale_tasks


async def batch_corrupt_tasks(
    client: HabiticaClient,
    llm_client: LLMClient,
    tasks: List[Dict[str, Any]],
    max_batch_size: int = 10,
) -> int:
    """
    批量黑化任务

    Args:
        client: Habitica 客户端
        llm_client: LLM 客户端
        tasks: 任务列表
        max_batch_size: 最大批量大小

    Returns:
        成功更新的任务数量
    """
    if not tasks:
        return 0

    # 分批处理
    batches = [
        tasks[i : i + max_batch_size] for i in range(0, len(tasks), max_batch_size)
    ]

    total_updated = 0

    for batch in batches:
        try:
            # 调用 LLM 批量黑化
            result = await llm_client.batch_corrupt_tasks(
                tasks=batch,
                style=settings.forge_style,
            )

            # 并发更新任务
            semaphore = asyncio.Semaphore(3)

            async def update_task(task_item):
                async with semaphore:
                    try:
                        # 查找对应的黑化结果
                        corrupted = None
                        for ct in result.tasks:
                            if ct.task_id.startswith(task_item["id"][:8]):
                                corrupted = ct
                                break

                        if corrupted:
                            # 计算新的腐烂等级
                            new_level = min(
                                task_item["corruption_level"] + 1,
                                MAX_CORRUPTION_LEVEL,
                            )

                            # 构建更新数据
                            updates = {
                                "text": corrupted.corrupted_text,
                                "notes": add_corruption_marker(
                                    task_item["notes"], new_level
                                ),
                            }

                            await client.update_task(task_item["id"], **updates)
                            logger.info(
                                f"Corrupted task {task_item['id'][:8]}: "
                                f"'{task_item['text']}' -> '{corrupted.corrupted_text}'"
                            )
                            return True
                    except Exception as e:
                        logger.error(
                            f"Failed to update task {task_item['id'][:8]}: {e}"
                        )
                        return False

                return False

            # 并发执行更新
            results = await asyncio.gather(
                *[update_task(task) for task in batch],
                return_exceptions=True,
            )

            total_updated += sum(1 for r in results if r is True)

        except Exception as e:
            logger.error(f"Batch corruption failed: {e}")

    return total_updated


async def run_scanner(force: bool = False) -> bool:
    """
    运行扫描器

    Args:
        force: 是否强制扫描

    Returns:
        是否成功
    """
    if not should_scan(force):
        logger.debug("Scan not needed yet")
        return True

    try:
        async with HabiticaClient() as habitica_client:
            # 获取过期任务
            stale_tasks = await fetch_stale_tasks(habitica_client)

            if not stale_tasks:
                logger.info("No stale tasks found")
                set_last_scan_time()
                return True

            # 批量黑化
            async with LLMClient() as llm_client:
                updated_count = await batch_corrupt_tasks(
                    habitica_client,
                    llm_client,
                    stale_tasks,
                )

            logger.info(f"Corruption scan completed: {updated_count} tasks updated")
            set_last_scan_time()
            return True

    except Exception as e:
        logger.error(f"Scanner failed: {e}")
        return False


def spawn_background_scanner() -> bool:
    """
    在后台启动扫描器（Fire-and-Forget）

    Returns:
        是否成功启动
    """
    try:
        python_executable = sys.executable

        cmd = [
            python_executable,
            "-m",
            "habitica_forge.schedule.scanner",
            "--force",
        ]

        # 在后台启动进程
        kwargs = {}

        if sys.platform == "win32":
            kwargs["creationflags"] = (
                subprocess.DETACHED_PROCESS
                | subprocess.CREATE_NO_WINDOW
                | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            kwargs["start_new_session"] = True

        with open(os.devnull, "w") as devnull:
            subprocess.Popen(
                cmd,
                stdout=devnull,
                stderr=devnull,
                stdin=subprocess.DEVNULL,
                **kwargs,
            )

        logger.info("Spawned background corruption scanner")
        return True

    except Exception as e:
        logger.error(f"Failed to spawn scanner: {e}")
        return False


def main():
    """脚本入口"""
    parser = argparse.ArgumentParser(description="深渊腐烂扫描器")
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="强制执行扫描，忽略时间间隔",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        help="日志级别 (默认 WARNING)",
    )

    args = parser.parse_args()

    # 初始化日志
    init_logging(level=args.log_level)

    # 运行扫描器
    success = asyncio.run(run_scanner(force=args.force))

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
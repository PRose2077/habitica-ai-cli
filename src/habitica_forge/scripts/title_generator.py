"""后台称号生成脚本

这是一个独立可执行的脚本，用于在后台生成称号并挂载到任务上。
通过 subprocess.Popen 在后台静默运行，不阻塞主进程。

使用方式:
    python -m habitica_forge.scripts.title_generator <task_id> <task_text> [--style Cyberpunk]
"""

import argparse
import asyncio
import sys
from typing import List, Optional

# 添加项目根目录到 sys.path
from habitica_forge.ai.llm_client import LLMClient
from habitica_forge.clients.habitica import HabiticaClient
from habitica_forge.core.bounty import (
    make_pending_tag_name,
    parse_wall_tags,
)
from habitica_forge.core.config import settings
from habitica_forge.utils.logger import get_logger, init_logging

logger = get_logger(__name__)


async def generate_and_attach_title(
    task_id: str,
    task_text: str,
    style: Optional[str] = None,
) -> bool:
    """
    生成称号并挂载到任务

    Args:
        task_id: 任务 ID
        task_text: 任务内容
        style: 游戏化风格

    Returns:
        是否成功
    """
    style = style or settings.forge_style

    try:
        async with HabiticaClient() as habitica_client:
            # 获取现有称号
            tags = await habitica_client.get_tags()
            wall_tags = parse_wall_tags([{"id": t.id, "name": t.name} for t in tags])
            existing_titles = [wt.title for wt in wall_tags]

            logger.info(f"Existing titles: {existing_titles}")

            # 调用 LLM 生成称号
            async with LLMClient() as llm_client:
                result = await llm_client.generate_title(
                    task_text=task_text,
                    existing_titles=existing_titles,
                    style=style,
                )

            logger.info(f"Generated title: {result.title_name}")

            # 创建待激活标签
            tag_name = make_pending_tag_name(result.title_name)
            tag = await habitica_client.get_or_create_tag(tag_name)

            # 将标签挂载到任务
            await habitica_client.add_tag_to_task(task_id, tag.id)

            logger.info(f"Title tag '{tag_name}' attached to task {task_id}")
            return True

    except Exception as e:
        logger.error(f"Failed to generate title: {e}")
        return False


def main():
    """脚本入口"""
    parser = argparse.ArgumentParser(
        description="后台称号生成脚本"
    )
    parser.add_argument(
        "task_id",
        help="任务 ID"
    )
    parser.add_argument(
        "task_text",
        help="任务内容"
    )
    parser.add_argument(
        "--style",
        default=None,
        help="游戏化风格 (默认从配置读取)"
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        help="日志级别 (默认 WARNING)"
    )

    args = parser.parse_args()

    # 初始化日志
    init_logging(level=args.log_level)

    # 运行异步任务
    success = asyncio.run(
        generate_and_attach_title(
            task_id=args.task_id,
            task_text=args.task_text,
            style=args.style,
        )
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
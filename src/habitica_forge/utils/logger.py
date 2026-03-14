"""终端渲染与日志系统"""

import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

# 检测是否在 Windows 下运行
IS_WINDOWS = sys.platform == "win32"

# 自定义主题
custom_theme = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red bold",
        "critical": "red bold reverse",
        "success": "green",
        "highlight": "magenta",
        "title": "bold blue",
        "label": "dim cyan",
    }
)

# 全局 Console 实例
# Windows 下需要特殊处理以支持 Unicode
console = Console(
    theme=custom_theme,
    force_terminal=True,
    legacy_windows=False if IS_WINDOWS else None,
)


class SensitiveDataFilter(logging.Filter):
    """敏感数据过滤器，脱敏 API Key 和 Token"""

    # 匹配常见敏感数据模式
    SENSITIVE_PATTERNS = [
        # API Keys (各种格式)
        (re.compile(r"(api[_-]?key|apikey)[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9_\-]{20,}", re.I), "API_KEY_REDACTED"),
        # Tokens
        (re.compile(r"(token|access_token|auth_token)[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9_\-]{20,}", re.I), "TOKEN_REDACTED"),
        # UUID 格式的敏感数据
        (re.compile(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", re.I), "UUID_REDACTED"),
        # Bearer tokens
        (re.compile(r"Bearer\s+[a-zA-Z0-9_\-\.]+"), "Bearer REDACTED"),
        # x-api-user 和 x-api-key 请求头
        (re.compile(r"x-api-user[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9_\-]+", re.I), "x-api-user=REDACTED"),
        (re.compile(r"x-api-key[\"']?\s*[:=]\s*[\"']?[a-zA-Z0-9_\-]+", re.I), "x-api-key=REDACTED"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """过滤日志记录中的敏感数据"""
        if record.msg:
            record.msg = self._redact(str(record.msg))
        if record.args:
            record.args = tuple(
                self._redact(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True

    def _redact(self, text: str) -> str:
        """替换文本中的敏感数据"""
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            text = pattern.sub(f"[{replacement}]", text)
        return text


def setup_logger(
    name: Optional[str] = None,
    level: str = "INFO",
    log_file: Optional[Path] = None,
) -> logging.Logger:
    """
    设置日志器

    Args:
        name: 日志器名称，默认为根日志器
        level: 日志级别
        log_file: 日志文件路径，默认为 ~/.config/habitica-forge/forge.log

    Returns:
        配置好的日志器
    """
    logger = logging.getLogger(name)

    # 避免重复配置
    if logger.handlers:
        return logger

    # 设置日志级别
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # 创建敏感数据过滤器
    sensitive_filter = SensitiveDataFilter()

    # 控制台处理器 - 使用 Rich
    console_handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        markup=True,
    )
    console_handler.setLevel(log_level)
    console_handler.addFilter(sensitive_filter)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    # 文件处理器
    if log_file is None:
        log_dir = Path.home() / ".config" / "habitica-forge"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "forge.log"

    file_handler = logging.FileHandler(
        log_file,
        encoding="utf-8",
        mode="a",
    )
    file_handler.setLevel(log_level)
    file_handler.addFilter(sensitive_filter)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(file_handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取日志器

    Args:
        name: 日志器名称

    Returns:
        日志器实例
    """
    return logging.getLogger(name)


def print_success(message: str) -> None:
    """打印成功消息"""
    console.print(f"[success][OK][/success] {message}")


def print_error(message: str) -> None:
    """打印错误消息"""
    console.print(f"[error][X][/error] {message}")


def print_warning(message: str) -> None:
    """打印警告消息"""
    console.print(f"[warning][!][/warning] {message}")


def print_info(message: str) -> None:
    """打印信息消息"""
    console.print(f"[info][i][/info] {message}")


def print_highlight(message: str) -> None:
    """打印高亮消息"""
    console.print(f"[highlight]{message}[/]")


def print_title(message: str) -> None:
    """打印标题"""
    console.print(f"\n[title]{message}[/]\n")


def print_table(
    headers: list[str],
    rows: list[list[str]],
    title: Optional[str] = None,
) -> None:
    """
    打印表格

    Args:
        headers: 表头
        rows: 数据行
        title: 表格标题
    """
    from rich.table import Table

    table = Table(title=title, show_header=True, header_style="bold cyan")
    for header in headers:
        table.add_column(header)
    for row in rows:
        table.add_row(*row)
    console.print(table)


def print_panel(message: str, title: Optional[str] = None, style: str = "blue") -> None:
    """
    打印面板

    Args:
        message: 消息内容
        title: 面板标题
        style: 面板样式
    """
    from rich.panel import Panel

    panel = Panel(message, title=title, border_style=style)
    console.print(panel)


# 初始化根日志器（延迟初始化，避免在导入时读取配置）
_logger_initialized = False


def init_logging(level: str = "INFO") -> None:
    """初始化全局日志系统"""
    global _logger_initialized
    if _logger_initialized:
        return
    setup_logger(level=level)
    _logger_initialized = True
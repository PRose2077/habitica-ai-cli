"""交互式拆解界面"""

import sys
import os
from typing import List, Optional

import questionary
from questionary import Style

from habitica_forge.ai.session import DecomposeSession
from habitica_forge.ai.llm_client import ChecklistSuggestion
from habitica_forge.styles.images import get_images_for_style, get_image_by_id, ImageResource
from habitica_forge.utils.logger import console, print_warning


def _setup_windows_terminal():
    """设置 Windows 终端环境变量，解决兼容性问题"""
    if sys.platform == 'win32':
        # 强制使用 Windows 控制台 API
        os.environ.setdefault('PROMPT_TOOLKIT_NO_CPR', '1')


# 在模块加载时设置终端环境
_setup_windows_terminal()


# 自定义 questionary 样式
CUSTOM_STYLE = Style([
    ('qmark', 'fg:#673ab7 bold'),
    ('question', 'bold'),
    ('answer', 'fg:#f44336 bold'),
    ('pointer', 'fg:#673ab7 bold'),
    ('highlighted', 'fg:#673ab7 bold'),
    ('selected', 'fg:#66bb6a'),
    ('separator', 'fg:#cc5454'),
    ('instruction', 'fg:#8d8d8d'),
    ('text', ''),
])


def _safe_ask(prompt):
    """
    安全地执行 questionary 提示，处理 Windows 终端兼容性问题

    Args:
        prompt: questionary 提示对象

    Returns:
        用户输入的结果
    """
    try:
        return prompt.unsafe_ask()
    except Exception as e:
        # 如果 prompt_toolkit 失败，尝试使用简单的 input()
        error_msg = str(e)
        if "Windows console" in error_msg or "xterm" in error_msg:
            console.print(f"\n[yellow]检测到终端兼容性问题，切换到简单输入模式[/]")
            # 使用简化的输入方式
            if hasattr(prompt, 'message'):
                console.print(f"\n{prompt.message}")
            return input("> ")
        raise


class InteractiveDecomposeUI:
    """交互式拆解 UI 管理器

    提供多轮对话式的任务拆解交互界面，
    支持预览、编辑、删除、添加子任务、添加图片等操作。
    """

    def __init__(self, session: DecomposeSession, style: str = "normal"):
        """初始化 UI 管理器

        Args:
            session: 当前拆解会话
            style: 当前风格
        """
        self.session = session
        self.style = style
        self._modified = False

    def render_preview(self) -> None:
        """渲染当前拆解结果预览（委托书样式）"""
        console.clear()
        console.print("\n[bold cyan]═══════════════════════════════════════[/]")
        console.print("[bold cyan]         任务委托书预览               [/]")
        console.print("[bold cyan]═══════════════════════════════════════[/]\n")

        result = self.session.current_result

        # 任务类型标签
        if result.quest_type:
            type_labels = {
                "main": "[bold green]【主线任务】[/]",
                "side": "[bold blue]【支线任务】[/]",
                "legendary": "[bold magenta]【传奇任务】[/]",
            }
            console.print(type_labels.get(result.quest_type, ""))

        # 任务标题
        console.print(f"[bold yellow]▶ {result.quest_title or result.task_title}[/]")

        # 任务属性行
        attrs = []
        if result.archetype:
            archetype_names = {
                "cleanup": "清理", "repair": "修复", "explore": "探索",
                "craft": "制作", "communicate": "沟通", "learn": "学习",
                "battle": "战斗", "supply": "补给",
            }
            attrs.append(f"类型: [cyan]{archetype_names.get(result.archetype, result.archetype)}[/]")
        if result.location:
            attrs.append(f"地点: [green]{result.location}[/]")

        if attrs:
            console.print(f"\n[dim]{' │ '.join(attrs)}[/]")

        # 任务备注
        if result.task_notes:
            console.print(f"\n[dim italic]{result.task_notes}[/]")

        # 建议优先级
        priority_style = {
            "trivial": "dim",
            "easy": "green",
            "medium": "yellow",
            "hard": "red bold",
        }.get(result.suggested_priority, "white")
        console.print(f"[bold]难度: [/][{priority_style}]{result.suggested_priority}[/]")

        # 已选择的图片
        if result.image_ids:
            console.print(f"\n[bold]已选择图片 ({len(result.image_ids)}):[/]")
            for img_id in result.image_ids:
                img = get_image_by_id(img_id)
                if img:
                    console.print(f"  🖼️ [cyan]{img.title}[/] [dim]({img_id})[/]")

        # 章节化子任务
        if result.chapters:
            console.print(f"\n[bold]任务阶段:[/]")
            for chapter in result.chapters:
                console.print(f"\n  [bold cyan]阶段 {chapter.chapter_number}: {chapter.chapter_title}[/]")
                for item in chapter.items:
                    item_style = {
                        "trivial": "dim",
                        "easy": "green",
                        "medium": "yellow",
                        "hard": "red",
                    }.get(item.priority, "white")
                    console.print(f"    [dim]○[/] [{item_style}]{item.text}[/]")
        elif result.checklist:
            console.print(f"\n[bold]任务步骤 ({len(result.checklist)}):[/]")
            for i, item in enumerate(result.checklist, 1):
                item_style = {
                    "trivial": "dim",
                    "easy": "green",
                    "medium": "yellow",
                    "hard": "red",
                }.get(item.priority, "white")
                console.print(f"  [yellow]{i}[/]. [{item_style}]{item.text}[/]")
        else:
            console.print("\n[dim]无子任务[/]")

        # 传奇任务提示
        if result.is_legendary:
            console.print("\n[bold magenta]⚠ 这是一个传奇任务，建议分阶段完成！[/]")

        if self._modified:
            console.print("\n[dim italic](已修改)[/]")

        console.print("\n[bold cyan]═══════════════════════════════════════[/]")
        console.print()

    def main_menu(self) -> str:
        """显示主菜单并获取用户选择

        Returns:
            用户选择的操作标识
        """
        choices = [
            questionary.Choice("确认提交", value="confirm", shortcut_key="a"),
            questionary.Choice("修改子任务", value="edit_checklist", shortcut_key="m"),
            questionary.Choice("添加子任务", value="add_checklist", shortcut_key="n"),
            questionary.Choice("删除子任务", value="delete_checklist", shortcut_key="d"),
            questionary.Choice("修改任务标题", value="edit_title", shortcut_key="t"),
            questionary.Choice("修改任务备注", value="edit_notes", shortcut_key="o"),
            questionary.Choice("调整任务优先级", value="edit_priority", shortcut_key="p"),
            questionary.Choice("添加图片", value="add_image", shortcut_key="i"),
            questionary.Choice("移除图片", value="remove_image", shortcut_key="x"),
            questionary.Choice("与 AI 对话调整", value="ai_refine", shortcut_key="r"),
            questionary.Choice("查看对话历史", value="show_history", shortcut_key="h"),
            questionary.Choice("放弃退出", value="quit", shortcut_key="q"),
        ]

        result = _safe_ask(questionary.select(
            "请选择操作:",
            choices=choices,
            style=CUSTOM_STYLE,
        ))

        return result or "quit"

    def select_checklist_item(self) -> Optional[int]:
        """选择一个子任务

        Returns:
            子任务索引，如果取消则返回 None
        """
        checklist = self.session.current_result.checklist
        if not checklist:
            print_warning("没有子任务可选择")
            return None

        choices = [
            questionary.Choice(
                f"{i}. {item.text} [{item.priority}]",
                value=i - 1,
            )
            for i, item in enumerate(checklist, 1)
        ]
        choices.append(questionary.Choice("返回", value=-1))

        result = _safe_ask(questionary.select(
            "选择要操作的子任务:",
            choices=choices,
            style=CUSTOM_STYLE,
        ))

        return result if result != -1 else None

    def edit_checklist_item(self, index: int) -> None:
        """编辑指定子任务

        Args:
            index: 子任务索引
        """
        item = self.session.current_result.checklist[index]

        # 选择操作
        action = _safe_ask(questionary.select(
            f"编辑子任务: {item.text}",
            choices=[
                questionary.Choice("修改内容", value="text"),
                questionary.Choice("修改难度", value="priority"),
                questionary.Choice("上移", value="up"),
                questionary.Choice("下移", value="down"),
                questionary.Choice("删除", value="delete"),
                questionary.Choice("返回", value="back"),
            ],
            style=CUSTOM_STYLE,
        ))

        if action is None or action == "back":
            return

        if action == "text":
            new_text = _safe_ask(questionary.text(
                "新的子任务内容:",
                default=item.text,
                style=CUSTOM_STYLE,
            ))
            if new_text:
                item.text = new_text
                self._modified = True

        elif action == "priority":
            new_priority = _safe_ask(questionary.select(
                "选择难度:",
                choices=["trivial", "easy", "medium", "hard"],
                default=item.priority,
                style=CUSTOM_STYLE,
            ))
            if new_priority:
                item.priority = new_priority
                self._modified = True

        elif action == "up":
            if index > 0:
                checklist = self.session.current_result.checklist
                checklist[index], checklist[index - 1] = checklist[index - 1], checklist[index]
                self._modified = True

        elif action == "down":
            checklist = self.session.current_result.checklist
            if index < len(checklist) - 1:
                checklist[index], checklist[index + 1] = checklist[index + 1], checklist[index]
                self._modified = True

        elif action == "delete":
            if _safe_ask(questionary.confirm("确定删除此子任务?", default=False, style=CUSTOM_STYLE)):
                self.session.current_result.checklist.pop(index)
                self._modified = True

    def add_checklist_item(self) -> None:
        """添加新子任务"""
        text = _safe_ask(questionary.text(
            "输入新子任务内容:",
            style=CUSTOM_STYLE,
        ))

        if text:
            priority = _safe_ask(questionary.select(
                "选择难度:",
                choices=["trivial", "easy", "medium", "hard"],
                default="easy",
                style=CUSTOM_STYLE,
            ))

            if priority:
                self.session.current_result.checklist.append(
                    ChecklistSuggestion(text=text, priority=priority)
                )
                self._modified = True

    def delete_checklist_item(self) -> None:
        """删除子任务"""
        index = self.select_checklist_item()
        if index is not None:
            if _safe_ask(questionary.confirm("确定删除此子任务?", default=False, style=CUSTOM_STYLE)):
                self.session.current_result.checklist.pop(index)
                self._modified = True

    def edit_title(self) -> None:
        """编辑任务标题"""
        new_title = _safe_ask(questionary.text(
            "新的任务标题:",
            default=self.session.current_result.task_title,
            style=CUSTOM_STYLE,
        ))

        if new_title:
            self.session.update_title(new_title)
            self._modified = True

    def edit_notes(self) -> None:
        """编辑任务备注"""
        current_notes = self.session.current_result.task_notes or ""
        new_notes = _safe_ask(questionary.text(
            "新的任务备注 (留空则清除):",
            default=current_notes,
            style=CUSTOM_STYLE,
        ))

        if new_notes is not None:
            self.session.update_notes(new_notes if new_notes else None)
            self._modified = True

    def edit_priority(self) -> None:
        """编辑任务优先级"""
        new_priority = _safe_ask(questionary.select(
            "选择任务难度:",
            choices=["trivial", "easy", "medium", "hard"],
            default=self.session.current_result.suggested_priority,
            style=CUSTOM_STYLE,
        ))

        if new_priority:
            self.session.update_priority(new_priority)
            self._modified = True

    def get_refine_context(self) -> Optional[str]:
        """获取用户提供的额外上下文

        Returns:
            用户输入的上下文，如果取消则返回 None
        """
        console.print("\n[dim]请提供额外信息，帮助 AI 更好地理解您的需求:[/]")
        return _safe_ask(questionary.text(
            "额外上下文 (如: 需要在下午完成、使用 Python 等):",
            style=CUSTOM_STYLE,
        ))

    def get_natural_feedback(self) -> Optional[str]:
        """获取用户的自然语言反馈（REPL 模式）

        Returns:
            用户输入的反馈，如果取消则返回 None
        """
        console.print("\n[dim]直接告诉 AI 您想要什么样的调整，或输入 'done' 确认提交:[/]")

        result = _safe_ask(questionary.text(
            "您的反馈:",
            style=CUSTOM_STYLE,
        ))

        if result is None:
            return None

        result = result.strip()
        if result.lower() in ("done", "确认", "好", "可以", "ok", "确认提交"):
            return "CONFIRM"

        return result if result else None

    def confirm_quit(self) -> bool:
        """确认退出

        Returns:
            True 如果用户确认退出
        """
        if self._modified:
            return _safe_ask(questionary.confirm(
                "您有未保存的修改，确定要放弃吗?",
                default=False,
                style=CUSTOM_STYLE,
            )) or False
        return True

    def show_conversation_history(self) -> None:
        """显示对话历史"""
        history = self.session.conversation_history
        if not history:
            console.print("\n[dim]暂无对话历史[/]")
            return

        console.print("\n[bold cyan]═══════════════════════════════════════[/]")
        console.print("[bold cyan]           对话历史                     [/]")
        console.print("[bold cyan]═══════════════════════════════════════[/]\n")

        for msg in history:
            if msg["role"] == "user":
                console.print(f"[bold green]您:[/] {msg['content']}")
            else:
                console.print(f"[bold blue]AI:[/] {msg['content']}")
            console.print()

    def add_image(self) -> None:
        """添加图片到任务"""
        # 获取当前风格的可用图片
        images = get_images_for_style(self.style, enabled_only=True)

        if not images:
            print_warning("当前风格没有可用的图片资源")
            return

        # 过滤掉已选择的图片
        current_ids = set(self.session.current_result.image_ids)
        available_images = [img for img in images if img.id not in current_ids]

        if not available_images:
            print_warning("所有图片都已被选择")
            return

        # 构建选择列表
        choices = [
            questionary.Choice(
                f"{img.title} - {img.description[:30]}{'...' if len(img.description) > 30 else ''}",
                value=img.id,
            )
            for img in available_images
        ]
        choices.append(questionary.Choice("返回", value="__back__"))

        selected_id = _safe_ask(questionary.select(
            "选择要添加的图片:",
            choices=choices,
            style=CUSTOM_STYLE,
        ))

        if selected_id and selected_id != "__back__":
            self.session.current_result.image_ids.append(selected_id)
            self._modified = True
            console.print(f"\n[green]已添加图片: {selected_id}[/]")

    def remove_image(self) -> None:
        """移除已选择的图片"""
        current_ids = self.session.current_result.image_ids

        if not current_ids:
            print_warning("没有已选择的图片")
            return

        # 构建选择列表
        choices = []
        for img_id in current_ids:
            img = get_image_by_id(img_id)
            if img:
                choices.append(questionary.Choice(
                    f"{img.title} ({img_id})",
                    value=img_id,
                ))

        if not choices:
            print_warning("无法找到已选择的图片信息")
            return

        choices.append(questionary.Choice("返回", value="__back__"))

        selected_id = _safe_ask(questionary.select(
            "选择要移除的图片:",
            choices=choices,
            style=CUSTOM_STYLE,
        ))

        if selected_id and selected_id != "__back__":
            self.session.current_result.image_ids.remove(selected_id)
            self._modified = True
            console.print(f"\n[green]已移除图片: {selected_id}[/]")
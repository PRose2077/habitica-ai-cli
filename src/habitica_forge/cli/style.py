"""风格切换命令模块"""

import typer

from habitica_forge.core.style import (
    get_all_styles,
    get_available_styles,
    get_current_style,
    is_gamified_style,
    set_style,
)
from habitica_forge.styles import get_style_display_name, normalize_style
from habitica_forge.utils.logger import console, print_error, print_info, print_success

# 创建风格命令子应用
style_app = typer.Typer(name="style", help="游戏化风格管理")


@style_app.callback(invoke_without_command=True)
def style_callback(ctx: typer.Context):
    """游戏化风格管理"""
    # 如果没有子命令，显示当前风格
    if ctx.invoked_subcommand is None:
        show_current_style()


def show_current_style():
    """显示当前风格"""
    current = get_current_style()
    display_name = get_style_display_name(current)

    console.print()
    console.print(f"[label]当前风格:[/] [bold]{display_name}[/] ({current})")

    if is_gamified_style(current):
        console.print("[dim]游戏化模式已启用，AI 文案将带有风格化元素[/]")
    else:
        console.print("[dim]正常模式，AI 文案将保持克制、直接的风格[/]")

    console.print()
    console.print("[dim]使用 [bold]forge style list[/] 查看所有可用风格[/]")
    console.print("[dim]使用 [bold]forge style switch <风格名>[/] 切换风格[/]")


@style_app.command("list")
def list_styles():
    """显示所有可用风格"""
    current = get_current_style()
    styles = get_all_styles()

    console.print()
    console.print("[bold]可用风格列表:[/]")
    console.print()

    for style_info in styles:
        name = style_info["name"]
        display_name = style_info["display_name"]
        description = style_info["description"]

        if name == current:
            console.print(f"  [bold green]* {display_name}[/] [dim]({name})[/] - {description}")
        else:
            console.print(f"    {display_name} [dim]({name})[/] - {description}")

    console.print()
    console.print(f"[dim]当前使用: [bold]{get_style_display_name(current)}[/][/]")
    console.print()


@style_app.command("switch")
def switch_style(
    style_name: str = typer.Argument(..., help="风格名称（查看 forge style list 获取所有可用风格）"),
):
    """
    切换游戏化风格

    切换后立即生效，后续 AI 文案将使用新风格。

    示例:
        forge style switch normal      # 切换到正常风格
        forge style switch cyberpunk   # 切换到赛博朋克风格
    """
    # 标准化风格名称
    normalized = normalize_style(style_name)

    # 检查风格是否有效
    available = get_available_styles()
    if normalized not in available:
        print_error(f"无效的风格: {style_name}")
        console.print()
        console.print("可用风格:")
        for s in available:
            console.print(f"  - {s}")
        raise typer.Exit(1)

    # 获取当前风格
    current = get_current_style()

    if normalized == current:
        print_info(f"已经是 [bold]{get_style_display_name(current)}[/] 风格")
        return

    # 切换风格
    success = set_style(normalized)

    if success:
        display_name = get_style_display_name(normalized)
        print_success(f"风格已切换为: [bold]{display_name}[/] ({normalized})")

        console.print()
        if is_gamified_style(normalized):
            console.print("[dim]游戏化模式已启用！AI 文案将带有风格化元素。[/]")
        else:
            console.print("[dim]正常模式已启用！AI 文案将保持克制、直接的风格。[/]")
    else:
        print_error("切换风格失败")
        raise typer.Exit(1)
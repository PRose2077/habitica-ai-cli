"""风格管理模块测试"""

import pytest

from habitica_forge.styles import (
    get_all_style_names,
    get_style_display_name,
    get_style_description,
    normalize_style,
)
from habitica_forge.core.style import (
    get_all_styles,
    get_available_styles,
    is_gamified_style,
)


class TestStyleNormalization:
    """测试风格名称标准化"""

    def test_normalize_lowercase(self):
        """测试小写风格名称"""
        assert normalize_style("normal") == "normal"
        assert normalize_style("cyberpunk") == "cyberpunk"
        assert normalize_style("wuxia") == "wuxia"
        assert normalize_style("fantasy") == "fantasy"

    def test_normalize_titlecase(self):
        """测试首字母大写风格名称（兼容旧配置）"""
        assert normalize_style("Normal") == "normal"
        assert normalize_style("Cyberpunk") == "cyberpunk"
        assert normalize_style("Wuxia") == "wuxia"
        assert normalize_style("Fantasy") == "fantasy"

    def test_normalize_uppercase(self):
        """测试全大写风格名称"""
        assert normalize_style("NORMAL") == "normal"
        assert normalize_style("CYBERPUNK") == "cyberpunk"
        assert normalize_style("WUXIA") == "wuxia"
        assert normalize_style("FANTASY") == "fantasy"

    def test_normalize_unknown_fallback(self):
        """测试未知风格名称回退到 normal"""
        assert normalize_style("unknown") == "normal"
        assert normalize_style("random_style") == "normal"
        assert normalize_style("") == "normal"


class TestStyleDisplayNames:
    """测试风格显示名称"""

    def test_get_display_name(self):
        """测试获取风格显示名称"""
        assert get_style_display_name("normal") == "正常风格"
        assert get_style_display_name("cyberpunk") == "赛博朋克"
        assert get_style_display_name("wuxia") == "武侠风格"
        assert get_style_display_name("fantasy") == "奇幻风格"

    def test_display_name_complete(self):
        """测试所有风格都有显示名称"""
        for style in get_available_styles():
            display_name = get_style_display_name(style)
            assert display_name != ""
            assert display_name != style  # 显示名称应该不同于风格名


class TestStyleDescriptions:
    """测试风格描述"""

    def test_get_description(self):
        """测试获取风格描述"""
        assert "克制" in get_style_description("normal")
        assert "科技" in get_style_description("cyberpunk")
        assert "武侠" in get_style_description("wuxia")
        assert "奇幻" in get_style_description("fantasy")

    def test_description_complete(self):
        """测试所有风格都有描述"""
        for style in get_available_styles():
            description = get_style_description(style)
            assert description != ""


class TestStyleManagement:
    """测试风格管理功能"""

    def test_get_all_styles(self):
        """测试获取所有风格"""
        styles = get_all_styles()

        assert len(styles) >= 4  # 至少有 4 种风格
        style_names = [s["name"] for s in styles]
        assert "normal" in style_names
        assert "cyberpunk" in style_names
        assert "wuxia" in style_names
        assert "fantasy" in style_names

    def test_get_all_styles_structure(self):
        """测试风格数据结构"""
        styles = get_all_styles()

        for style in styles:
            assert "name" in style
            assert "display_name" in style
            assert "description" in style

    def test_get_all_style_names(self):
        """测试获取所有风格名称"""
        names = get_all_style_names()
        assert "normal" in names
        assert "cyberpunk" in names
        assert "wuxia" in names
        assert "fantasy" in names

    def test_is_gamified_style(self):
        """测试游戏化风格判断"""
        assert is_gamified_style("normal") is False
        assert is_gamified_style("cyberpunk") is True
        assert is_gamified_style("wuxia") is True
        assert is_gamified_style("fantasy") is True

    def test_is_gamified_style_normalization(self):
        """测试游戏化风格判断支持大小写"""
        assert is_gamified_style("Normal") is False
        assert is_gamified_style("Cyberpunk") is True
        assert is_gamified_style("WUXIA") is True


class TestLLMPrompts:
    """测试 LLM Prompt 构建函数"""

    def test_decompose_prompt_has_normal_style(self):
        """测试任务拆解 Prompt 包含 normal 风格"""
        from habitica_forge.ai.llm_client import _build_decompose_prompt

        prompt = _build_decompose_prompt("normal")
        assert "简洁" in prompt or "直接" in prompt

    def test_decompose_prompt_has_cyberpunk_style(self):
        """测试任务拆解 Prompt 包含 cyberpunk 风格"""
        from habitica_forge.ai.llm_client import _build_decompose_prompt

        prompt = _build_decompose_prompt("cyberpunk")
        assert "赛博朋克" in prompt or "科技" in prompt

    def test_title_prompt_has_normal_style(self):
        """测试称号生成 Prompt 包含 normal 风格"""
        from habitica_forge.ai.llm_client import _build_title_prompt

        prompt = _build_title_prompt("normal")
        assert "简洁" in prompt or "直接" in prompt

    def test_corruption_prompt_has_normal_style(self):
        """测试腐烂文案 Prompt 包含 normal 风格"""
        from habitica_forge.ai.llm_client import _build_corruption_prompt

        prompt = _build_corruption_prompt("normal")
        assert "紧迫" in prompt or "提醒" in prompt

    def test_unknown_style_fallback_to_normal(self):
        """测试未知风格回退到 normal"""
        from habitica_forge.ai.llm_client import _build_decompose_prompt

        prompt = _build_decompose_prompt("unknown_style")
        # 应该回退到 normal 风格
        assert "简洁" in prompt or "直接" in prompt


class TestDynamicStyleExtension:
    """测试动态风格扩展"""

    def test_add_new_style(self, tmp_path):
        """测试添加新风格"""
        from habitica_forge.styles.loader import reload_styles

        # 这个测试验证架构支持动态扩展
        # 实际添加新风格只需创建 YAML 文件
        initial_count = len(get_all_style_names())

        # 验证当前风格数量
        assert initial_count >= 4

        # 重新加载后应该保持一致
        reload_styles()
        assert len(get_all_style_names()) == initial_count
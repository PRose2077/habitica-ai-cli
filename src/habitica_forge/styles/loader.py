"""风格配置加载器

从 YAML 文件加载风格配置，支持动态扩展风格。
只需在 styles/ 目录下添加 YAML 文件即可新增风格。
使用基础模板 + 风格变量的方式生成提示词。

V2 新增：
- 世界观词典系统 (Lexicon)
- 任务类型命名模板
- 任务上下文词典
- 图片资源词典
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from habitica_forge.quest.archetype import QuestArchetype
from habitica_forge.utils.logger import get_logger

logger = get_logger(__name__)

# 风格配置目录
STYLES_DIR = Path(__file__).parent

# 缓存
_style_cache: Dict[str, "StyleConfig"] = {}
_all_styles_cache: Optional[List["StyleConfig"]] = None
_case_map_cache: Optional[Dict[str, str]] = None
_base_template_cache: Optional[Dict] = None


# ============================================
# 模板渲染
# ============================================


def _load_base_template() -> Dict:
    """加载基础模板

    Returns:
        基础模板字典
    """
    global _base_template_cache

    if _base_template_cache is not None:
        return _base_template_cache

    template_file = STYLES_DIR / "base_template.yaml"

    if not template_file.exists():
        logger.warning(f"Base template not found: {template_file}")
        return {}

    try:
        with open(template_file, "r", encoding="utf-8") as f:
            _base_template_cache = yaml.safe_load(f) or {}
        return _base_template_cache
    except Exception as e:
        logger.error(f"Failed to load base template: {e}")
        return {}


def _render_template(template: str, variables: Dict) -> str:
    """渲染模板

    Args:
        template: 模板字符串，使用 {variable} 作为占位符
        variables: 变量字典

    Returns:
        渲染后的字符串
    """
    try:
        return template.format(**variables)
    except KeyError as e:
        logger.warning(f"Missing variable in template: {e}")
        return template
    except Exception as e:
        logger.error(f"Failed to render template: {e}")
        return template


def _render_prompts(style_data: Dict) -> Dict:
    """渲染提示词

    将风格变量应用到基础模板，生成最终提示词。

    Args:
        style_data: 风格配置数据（包含变量）

    Returns:
        渲染后的提示词字典
    """
    base_template = _load_base_template()
    variables = style_data.get("variables", {})

    if not base_template:
        # 如果没有基础模板，使用风格配置中的 prompts（向后兼容）
        return style_data.get("prompts", {})

    rendered = {}

    # 渲染 decompose
    if "decompose" in base_template:
        rendered["decompose"] = _render_template(base_template["decompose"], variables)

    # 渲染 title
    if "title" in base_template:
        rendered["title"] = _render_template(base_template["title"], variables)

    # 渲染 corruption
    if "corruption" in base_template:
        rendered["corruption"] = _render_template(base_template["corruption"], variables)

    # 渲染 refine
    if "refine" in base_template:
        refine_template = base_template["refine"]
        if isinstance(refine_template, dict):
            rendered["refine"] = {}
            for field_type, tmpl in refine_template.items():
                rendered["refine"][field_type] = _render_template(tmpl, variables)

    return rendered


# ============================================
# 词典类 (V2)
# ============================================


class Lexicon:
    """世界观词典

    包含任务动词、名词、地点、称号、敌人、稀有度等词典。
    """

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @property
    def verbs(self) -> Dict[str, List[str]]:
        """任务动词词典（按原型分类）"""
        return self._data.get("verbs", {})

    @property
    def nouns(self) -> Dict[str, List[str]]:
        """名词词典（按原型分类）"""
        return self._data.get("nouns", {})

    @property
    def locations(self) -> Dict[str, str]:
        """地点词典"""
        return self._data.get("locations", {})

    @property
    def titles(self) -> Dict[str, List[str]]:
        """称号词典（按领域分类）"""
        return self._data.get("titles", {})

    @property
    def enemies(self) -> Dict[str, str]:
        """敌人/挑战词典"""
        return self._data.get("enemies", {})

    @property
    def rarities(self) -> Dict[str, str]:
        """稀有度词典"""
        return self._data.get("rarities", {})

    def get_verbs_for_archetype(self, archetype: str) -> List[str]:
        """获取指定原型的动词列表

        Args:
            archetype: 原型名称（如 cleanup, repair）

        Returns:
            动词列表
        """
        return self.verbs.get(archetype, [])

    def get_nouns_for_archetype(self, archetype: str) -> List[str]:
        """获取指定原型的名词列表

        Args:
            archetype: 原型名称

        Returns:
            名词列表
        """
        return self.nouns.get(archetype, [])

    def get_location_mapping(self, location_key: str) -> str:
        """获取地点映射

        Args:
            location_key: 现实地点键

        Returns:
            游戏化地点名称，未找到时返回原键
        """
        return self.locations.get(location_key, location_key)

    def get_titles_for_domain(self, domain: str) -> List[str]:
        """获取指定领域的称号列表

        Args:
            domain: 领域名称（如 productivity, learning）

        Returns:
            称号列表
        """
        return self.titles.get(domain, self.titles.get("default", []))

    def get_enemy_name(self, enemy_type: str) -> str:
        """获取敌人/挑战名称

        Args:
            enemy_type: 敌人类型（如 procrastination）

        Returns:
            敌人名称
        """
        return self.enemies.get(enemy_type, self.enemies.get("default", enemy_type))

    def get_rarity_label(self, rarity: str) -> str:
        """获取稀有度标签

        Args:
            rarity: 稀有度级别（如 trivial, easy, medium）

        Returns:
            稀有度标签
        """
        return self.rarities.get(rarity, rarity)


class StyleTemplates:
    """风格命名模板

    包含 Habit/Daily/Todo 各自的命名模板。
    """

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @property
    def habit(self) -> Dict[str, str]:
        """Habit 模板"""
        return self._data.get("habit", {})

    @property
    def daily(self) -> Dict[str, str]:
        """Daily 模板"""
        return self._data.get("daily", {})

    @property
    def todo(self) -> Dict[str, str]:
        """Todo 模板"""
        return self._data.get("todo", {})

    def get_habit_template(self, template_type: str = "neutral") -> str:
        """获取 Habit 模板

        Args:
            template_type: 模板类型 (positive/negative/neutral)

        Returns:
            模板字符串
        """
        return self.habit.get(template_type, "{action}")

    def get_daily_template(self, template_type: str = "simple") -> str:
        """获取 Daily 模板

        Args:
            template_type: 模板类型 (with_location/simple/routine)

        Returns:
            模板字符串
        """
        return self.daily.get(template_type, "{action}")

    def get_todo_template(self, template_type: str = "simple") -> str:
        """获取 Todo 模板

        Args:
            template_type: 模板类型 (with_priority/with_location/simple/legendary)

        Returns:
            模板字符串
        """
        return self.todo.get(template_type, "{title}")


class ContextDictionary:
    """任务上下文词典

    定义不同上下文（工作、学习、家务等）的游戏化规则。
    """

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    @property
    def work(self) -> Dict[str, Any]:
        """工作上下文"""
        return self._data.get("work", {})

    @property
    def study(self) -> Dict[str, Any]:
        """学习上下文"""
        return self._data.get("study", {})

    @property
    def home(self) -> Dict[str, Any]:
        """家务上下文"""
        return self._data.get("home", {})

    @property
    def personal(self) -> Dict[str, Any]:
        """个人发展上下文"""
        return self._data.get("personal", {})

    def detect_context(self, text: str) -> Optional[str]:
        """从文本中检测上下文

        Args:
            text: 任务文本

        Returns:
            检测到的上下文名称（work/study/home/personal），未检测到返回 None
        """
        text_lower = text.lower()

        for context_name, context_data in self._data.items():
            hints = context_data.get("location_hints", [])
            for hint in hints:
                if hint.lower() in text_lower:
                    return context_name

        return None

    def get_context_data(self, context_name: str) -> Dict[str, Any]:
        """获取上下文数据

        Args:
            context_name: 上下文名称

        Returns:
            上下文数据字典
        """
        return self._data.get(context_name, {})

    def get_location_mapping(self, context_name: str) -> str:
        """获取上下文对应的地点映射

        Args:
            context_name: 上下文名称

        Returns:
            地点映射名称
        """
        context_data = self.get_context_data(context_name)
        return context_data.get("location_mapping", "")

    def get_verbs(self, context_name: str) -> List[str]:
        """获取上下文对应的动词

        Args:
            context_name: 上下文名称

        Returns:
            动词列表
        """
        context_data = self.get_context_data(context_name)
        return context_data.get("verbs", [])


class QualityBaseline:
    """风格质量基线

    包含标准输入输出样例，用于验证风格一致性。
    """

    def __init__(self, samples: List[Dict[str, Any]]):
        self._samples = samples

    @property
    def samples(self) -> List[Dict[str, Any]]:
        """获取所有样例"""
        return self._samples

    def get_samples_for_archetype(self, archetype: str) -> List[Dict[str, Any]]:
        """获取指定原型的样例

        Args:
            archetype: 原型名称

        Returns:
            样例列表
        """
        return [s for s in self._samples if s.get("archetype") == archetype]

    def get_samples_for_context(self, context: str) -> List[Dict[str, Any]]:
        """获取指定上下文的样例

        Args:
            context: 上下文名称

        Returns:
            样例列表
        """
        return [s for s in self._samples if s.get("context") == context]


# ============================================
# 配置类
# ============================================


class PromptConfig:
    """提示词配置"""

    def __init__(self, data: Dict):
        self._data = data

    @property
    def decompose(self) -> str:
        """任务拆解提示词"""
        return self._data.get("decompose", "")

    @property
    def title(self) -> str:
        """称号生成提示词"""
        return self._data.get("title", "")

    @property
    def corruption(self) -> str:
        """任务黑化提示词"""
        return self._data.get("corruption", "")

    def get_refine(self, field_type: str) -> str:
        """获取字段优化提示词

        Args:
            field_type: 字段类型 (title, notes, checklist)
        """
        refine = self._data.get("refine", {})
        if isinstance(refine, dict):
            return refine.get(field_type, refine.get("title", ""))
        return str(refine) if refine else ""


class StyleConfig:
    """风格配置

    V2 增强：
    - lexicon: 世界观词典
    - templates: 命名模板
    - context: 上下文词典
    - quality_baseline: 质量基线
    """

    def __init__(self, data: Dict, style_name: str):
        self._data = data
        self._name = style_name
        # 渲染提示词
        self._prompts = PromptConfig(_render_prompts(data))
        # V2 词典
        self._lexicon = Lexicon(data.get("lexicon", {}))
        self._templates = StyleTemplates(data.get("templates", {}))
        self._context = ContextDictionary(data.get("context", {}))
        self._quality_baseline = QualityBaseline(data.get("quality_baseline", []))

    @property
    def name(self) -> str:
        """风格名称"""
        return self._name

    @property
    def display_name(self) -> str:
        """显示名称"""
        return self._data.get("display_name", self._name)

    @property
    def description(self) -> str:
        """风格描述"""
        return self._data.get("description", "")

    @property
    def prompts(self) -> PromptConfig:
        """提示词配置"""
        return self._prompts

    @property
    def examples(self) -> Dict[str, List[str]]:
        """示例映射"""
        return self._data.get("examples", {})

    @property
    def variables(self) -> Dict:
        """风格变量"""
        return self._data.get("variables", {})

    # ============================================
    # V2 新增属性
    # ============================================

    @property
    def lexicon(self) -> Lexicon:
        """世界观词典"""
        return self._lexicon

    @property
    def templates(self) -> StyleTemplates:
        """命名模板"""
        return self._templates

    @property
    def context(self) -> ContextDictionary:
        """上下文词典"""
        return self._context

    @property
    def quality_baseline(self) -> QualityBaseline:
        """质量基线"""
        return self._quality_baseline

    # ============================================
    # V2 便捷方法
    # ============================================

    def get_verb_for_archetype(
        self, archetype: QuestArchetype, context: Optional[str] = None
    ) -> Optional[str]:
        """获取适合当前原型和上下文的动词

        Args:
            archetype: 任务原型
            context: 可选的上下文名称

        Returns:
            随机选择的动词，无匹配时返回 None
        """
        import random

        archetype_name = archetype.value if isinstance(archetype, QuestArchetype) else archetype

        # 先从原型词典获取
        verbs = self.lexicon.get_verbs_for_archetype(archetype_name)

        # 如果有上下文，也获取上下文动词
        if context:
            context_verbs = self.context.get_verbs(context)
            verbs = verbs + context_verbs

        if verbs:
            return random.choice(verbs)
        return None

    def get_noun_for_archetype(self, archetype: QuestArchetype) -> Optional[str]:
        """获取适合当前原型的名词

        Args:
            archetype: 任务原型

        Returns:
            随机选择的名词，无匹配时返回 None
        """
        import random

        archetype_name = archetype.value if isinstance(archetype, QuestArchetype) else archetype
        nouns = self.lexicon.get_nouns_for_archetype(archetype_name)

        if nouns:
            return random.choice(nouns)
        return None

    def gamify_location(self, location_key: str, context: Optional[str] = None) -> str:
        """游戏化地点名称

        Args:
            location_key: 现实地点键
            context: 可选的上下文名称

        Returns:
            游戏化后的地点名称
        """
        # 先尝试直接映射
        mapped = self.lexicon.get_location_mapping(location_key)
        if mapped != location_key:
            return mapped

        # 尝试从上下文获取
        if context:
            context_location = self.context.get_location_mapping(context)
            if context_location:
                return context_location

        return location_key

    def detect_task_context(self, text: str) -> Optional[str]:
        """检测任务上下文

        Args:
            text: 任务文本

        Returns:
            检测到的上下文名称
        """
        return self.context.detect_context(text)

    def get_habit_title_template(self, is_positive: bool = True) -> str:
        """获取 Habit 标题模板

        Args:
            is_positive: 是否为正向行为

        Returns:
            模板字符串
        """
        template_type = "positive" if is_positive else "negative"
        return self.templates.get_habit_template(template_type)

    def get_daily_title_template(self, has_location: bool = False) -> str:
        """获取 Daily 标题模板

        Args:
            has_location: 是否包含地点

        Returns:
            模板字符串
        """
        template_type = "with_location" if has_location else "simple"
        return self.templates.get_daily_template(template_type)

    def get_todo_title_template(
        self, has_priority: bool = False, is_legendary: bool = False
    ) -> str:
        """获取 Todo 标题模板

        Args:
            has_priority: 是否包含优先级
            is_legendary: 是否为传奇任务

        Returns:
            模板字符串
        """
        if is_legendary:
            return self.templates.get_todo_template("legendary")
        elif has_priority:
            return self.templates.get_todo_template("with_priority")
        else:
            return self.templates.get_todo_template("simple")


# ============================================
# 加载函数
# ============================================


def _load_style_config(style_name: str) -> Optional[StyleConfig]:
    """加载单个风格配置

    Args:
        style_name: 风格名称

    Returns:
        风格配置，如果不存在返回 None
    """
    config_file = STYLES_DIR / f"{style_name}.yaml"

    if not config_file.exists():
        logger.warning(f"Style config not found: {config_file}")
        return None

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            logger.warning(f"Empty style config: {config_file}")
            return None

        return StyleConfig(data, style_name)

    except Exception as e:
        logger.error(f"Failed to load style config {config_file}: {e}")
        return None


def get_style_config(style_name: str) -> StyleConfig:
    """获取风格配置

    优先从缓存读取，缓存未命中则加载配置文件。
    如果配置文件不存在，返回 normal 风格作为回退。

    Args:
        style_name: 风格名称

    Returns:
        风格配置
    """
    # 标准化风格名称
    normalized = style_name.lower()

    # 检查缓存
    if normalized in _style_cache:
        return _style_cache[normalized]

    # 加载配置
    config = _load_style_config(normalized)

    if config is None:
        # 回退到 normal 风格
        if normalized != "normal":
            logger.warning(f"Style '{style_name}' not found, fallback to 'normal'")
            return get_style_config("normal")
        # normal 也不存在，返回空配置
        config = StyleConfig({
            "name": "normal",
            "display_name": "正常风格",
            "description": "默认风格",
            "prompts": {},
        }, "normal")

    _style_cache[normalized] = config
    return config


def get_all_style_configs() -> List[StyleConfig]:
    """获取所有风格配置

    扫描 styles 目录下的所有 YAML 文件（排除 base_template.yaml）。

    Returns:
        风格配置列表
    """
    global _all_styles_cache

    if _all_styles_cache is not None:
        return _all_styles_cache

    configs = []

    for yaml_file in STYLES_DIR.glob("*.yaml"):
        style_name = yaml_file.stem
        # 跳过 base_template 和 images
        if style_name in ("base_template", "images"):
            continue
        config = get_style_config(style_name)
        if config:
            configs.append(config)

    _all_styles_cache = configs
    return configs


def reload_styles() -> None:
    """清除所有风格配置缓存

    用于热重载配置文件。
    """
    global _style_cache, _all_styles_cache, _case_map_cache, _base_template_cache
    _style_cache = {}
    _all_styles_cache = None
    _case_map_cache = None
    _base_template_cache = None
    logger.info("Style cache cleared")


# ============================================
# 动态风格查询函数
# ============================================


def get_all_style_names() -> List[str]:
    """获取所有风格名称列表

    Returns:
        风格名称列表，如 ["normal", "cyberpunk", "wuxia", "fantasy"]
    """
    configs = get_all_style_configs()
    return [c.name for c in configs]


def get_style_display_name(style: str) -> str:
    """获取风格的显示名称

    Args:
        style: 风格名称

    Returns:
        风格的中文显示名称
    """
    config = get_style_config(style)
    return config.display_name


def get_style_description(style: str) -> str:
    """获取风格的描述

    Args:
        style: 风格名称

    Returns:
        风格的描述文字
    """
    config = get_style_config(style)
    return config.description


def get_style_case_map() -> Dict[str, str]:
    """获取风格大小写映射表

    动态生成，支持新风格自动加入映射。

    Returns:
        大小写映射字典，如 {"normal": "normal", "Normal": "normal", ...}
    """
    global _case_map_cache

    if _case_map_cache is not None:
        return _case_map_cache

    case_map = {}
    for style_name in get_all_style_names():
        case_map[style_name] = style_name
        case_map[style_name.capitalize()] = style_name
        case_map[style_name.upper()] = style_name

    _case_map_cache = case_map
    return case_map


def normalize_style(style: str) -> str:
    """标准化风格名称

    将任意大小写的风格名称转换为标准小写形式。
    如果风格不存在，返回 "normal" 作为回退。

    Args:
        style: 风格名称（可以是任意大小写）

    Returns:
        标准化的风格名称
    """
    case_map = get_style_case_map()
    return case_map.get(style, "normal")
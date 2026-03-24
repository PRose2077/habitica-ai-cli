"""LLM 客户端: 封装 OpenAI 兼容协议"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, Field

from habitica_forge.core.config import settings
from habitica_forge.styles import get_style_config
from habitica_forge.utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """LLM 调用错误"""

    pass


class LLMClient:
    """
    OpenAI 兼容的 LLM 客户端

    支持异步调用和 JSON 结构化输出
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        """
        初始化 LLM 客户端

        Args:
            api_key: API Key，默认从配置读取
            base_url: API Base URL，默认从配置读取
            model: 模型名称，默认从配置读取
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.api_key = api_key or settings.llm_api_key
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.model = model or settings.llm_model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            # 禁用 httpx 的日志输出
            import logging
            logging.getLogger("httpx").setLevel(logging.WARNING)
            logging.getLogger("httpcore").setLevel(logging.WARNING)

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self._get_headers(),
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "LLMClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """
        发送聊天完成请求

        Args:
            messages: 消息列表
            response_format: 响应格式（如 {"type": "json_object"}）
            temperature: 温度参数
            **kwargs: 其他参数

        Returns:
            生成的文本内容

        Raises:
            LLMError: LLM 调用失败
        """
        client = await self._get_client()

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }

        if response_format:
            payload["response_format"] = response_format

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await client.post("/chat/completions", json=payload)
                response.raise_for_status()

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                logger.debug(f"LLM response: {content[:200]}...")
                return content

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code >= 500 and attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                raise LLMError(f"LLM API error: {e.response.status_code} - {e.response.text}") from e

            except httpx.RequestError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue
                raise LLMError(f"LLM request error: {e}") from e

            except (KeyError, IndexError) as e:
                raise LLMError(f"Invalid LLM response format: {e}") from e

        raise LLMError(f"Max retries exceeded: {last_error}")

    async def chat_completion_json(
        self,
        messages: List[Dict[str, str]],
        response_model: Optional[Type[T]] = None,
        temperature: float = 0.7,
        **kwargs,
    ) -> Dict[str, Any] | T:
        """
        发送聊天完成请求并返回 JSON

        Args:
            messages: 消息列表
            response_model: Pydantic 模型，用于验证响应
            temperature: 温度参数
            **kwargs: 其他参数

        Returns:
            解析后的 JSON 数据或 Pydantic 模型实例

        Raises:
            LLMError: LLM 调用失败或 JSON 解析失败
        """
        # 使用 JSON 模式
        content = await self.chat_completion(
            messages=messages,
            response_format={"type": "json_object"},
            temperature=temperature,
            **kwargs,
        )

        try:
            # 清理可能的 markdown 代码块
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)

            if response_model:
                return response_model.model_validate(data)
            return data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {content}")
            raise LLMError(f"Failed to parse JSON response: {e}") from e

    async def smart_decompose(
        self,
        task_text: str,
        style: str = "normal",
        existing_checklist: Optional[List[str]] = None,
        task_type: str = "todo",
    ) -> "SmartDecomposeResult":
        """
        智能拆解任务 (V2 委托书模式)

        V2 新增功能：
        - 生成双名结构 (real_title + quest_title)
        - 判断任务原型 (archetype)
        - 生成地点和奖励感
        - 章节化拆解
        - 图片候选
        - 验证游戏化约束

        Args:
            task_text: 任务内容
            style: 游戏化风格
            existing_checklist: 现有的 checklist 项（用于更新场景）
            task_type: 任务类型 (habit/daily/todo)

        Returns:
            拆解结果
        """
        system_prompt = _build_decompose_prompt(style, task_type)

        user_content = f"任务: {task_text}"
        if existing_checklist:
            user_content += f"\n\n现有的子任务:\n" + "\n".join(f"- {item}" for item in existing_checklist)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        result = await self.chat_completion_json(
            messages=messages,
            response_model=SmartDecomposeResult,
            temperature=0.8,
        )

        # V2: 验证并修复游戏化约束
        result = self._validate_and_fix_result(result, task_text)

        # V2: 应用风格化的地点和奖励
        result = self._apply_style_enhancements(result, style, task_text)

        logger.info(f"Smart decompose completed for: {task_text[:50]}...")
        return result

    def _apply_style_enhancements(
        self,
        result: "SmartDecomposeResult",
        style: str,
        original_text: str,
    ) -> "SmartDecomposeResult":
        """应用风格增强

        根据 V2 词典系统增强任务的游戏化效果。
        V2 阶段四：集成传奇任务检测和章节化。
        V2 阶段五：简化，移除元数据相关处理。

        Args:
            result: AI 生成的结果
            style: 风格名称
            original_text: 原始任务文本

        Returns:
            增强后的结果
        """
        from habitica_forge.styles import get_style_config
        from habitica_forge.quest.legendary import LegendaryDetector

        style_config = get_style_config(style)

        # 如果没有设置地点，尝试从上下文检测
        if not result.location:
            context = style_config.detect_task_context(original_text)
            if context:
                result.location = style_config.gamify_location(context, context)

        # 使用传奇任务检测器
        detector = LegendaryDetector(style)
        is_legendary, legendary_config = detector.detect(
            title=original_text,
            checklist_count=len(result.checklist),
            notes=result.task_notes,
            user_specified=result.quest_type if result.is_legendary else None,
        )

        if is_legendary and legendary_config:
            result.is_legendary = True
            result.quest_type = legendary_config.type.value

            # 应用传奇任务前缀
            if result.quest_title and not any(
                result.quest_title.startswith(p)
                for prefixes in [
                    ["【主线】", "【王命】", "【史诗】", "【核心】", "【重要】"],
                    ["【远征】", "【探索】", "【冒险】", "【长期项目】"],
                    ["【战役】", "【大战】", "【征讨】", "【多阶段】"],
                    ["【史诗】", "【传奇】", "【神话】", "【超算级】"],
                ]
                for p in prefixes
            ):
                result.quest_title = detector.apply_prefix(
                    result.quest_title,
                    legendary_config,
                )

            # 如果有章节，设置章节数
            if result.chapters:
                legendary_config.chapter_count = len(result.chapters)

        return result

    def _validate_and_fix_result(
        self,
        result: "SmartDecomposeResult",
        original_text: str,
    ) -> "SmartDecomposeResult":
        """验证并修复游戏化结果

        确保游戏化约束被满足：
        1. 标题存在
        2. 标题长度限制

        Args:
            result: AI 生成的结果
            original_text: 原始任务文本

        Returns:
            验证/修复后的结果
        """
        from habitica_forge.quest import truncate_title

        # 确保 quest_title 存在
        if not result.quest_title:
            result.quest_title = original_text

        # 确保标题长度
        result.quest_title = truncate_title(result.quest_title)
        result.task_title = result.quest_title

        return result

    async def refine_decompose_with_context(
        self,
        session: "DecomposeSession",
        user_context: str,
        style: str = "normal",
    ) -> "SmartDecomposeResult":
        """
        基于对话历史和用户新输入重新拆解任务

        支持多轮对话式交互，AI 会记住之前的调整和用户反馈。

        Args:
            session: 当前拆解会话
            user_context: 用户提供的额外上下文或反馈
            style: 游戏化风格

        Returns:
            更新后的拆解结果
        """
        system_prompt = _build_decompose_prompt(style)

        # 构建对话历史
        messages = [{"role": "system", "content": system_prompt}]

        # 添加原始任务
        messages.append({
            "role": "user",
            "content": f"任务: {session.original_input}"
        })

        # 添加历史对话（包含之前的调整）
        messages.extend(session.conversation_history)

        # 构建当前状态的详细描述
        current_result = session.current_result
        checklist_items = []
        for item in current_result.checklist:
            checklist_items.append(f"  - [{item.priority}] {item.text}")
        checklist_str = "\n".join(checklist_items) if checklist_items else "  (无)"

        current_state = f"""当前拆解结果:
- 任务标题: {current_result.task_title}
- 任务备注: {current_result.task_notes or '(无)'}
- 建议难度: {current_result.suggested_priority}
- 子任务:
{checklist_str}

用户反馈: {user_context}

请根据用户的反馈调整拆解结果。如果用户表示满意或确认，则保持当前结果基本不变。"""

        messages.append({"role": "user", "content": current_state})

        result = await self.chat_completion_json(
            messages=messages,
            response_model=SmartDecomposeResult,
            temperature=0.7,
        )

        # 更新会话历史（记录这次交互）
        session.add_user_message(user_context)

        # 生成简要的 AI 响应摘要
        changes = []
        if result.task_title != current_result.task_title:
            changes.append(f"标题改为: {result.task_title}")
        if result.task_notes != current_result.task_notes:
            changes.append(f"备注更新")
        if len(result.checklist) != len(current_result.checklist):
            changes.append(f"子任务数量: {len(result.checklist)} 个")

        if changes:
            session.add_assistant_message(f"已调整: {', '.join(changes)}")
        else:
            session.add_assistant_message("已根据您的反馈调整拆解结果")

        logger.info(f"Refined decompose for: {session.original_input[:30]}...")
        return result

    async def generate_title(
        self,
        task_text: str,
        existing_titles: List[str],
        style: str = "normal",
    ) -> "TitleGenerationResult":
        """
        生成新称号

        Args:
            task_text: 任务内容
            existing_titles: 现有称号列表
            style: 游戏化风格

        Returns:
            称号生成结果
        """
        system_prompt = _build_title_prompt(style)

        user_content = f"任务: {task_text}\n\n"
        if existing_titles:
            user_content += "现有称号:\n" + "\n".join(f"- {t}" for t in existing_titles)
        else:
            user_content += "现有称号: 无（这是第一个称号）"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        result = await self.chat_completion_json(
            messages=messages,
            response_model=TitleGenerationResult,
            temperature=0.9,  # 更高的温度增加创意
        )

        logger.info(f"Title generated: {result.title_name}")
        return result

    async def batch_corrupt_tasks(
        self,
        tasks: List[Dict[str, Any]],
        style: str = "normal",
    ) -> "BatchCorruptionResult":
        """
        批量黑化任务

        Args:
            tasks: 任务列表，每个任务包含 id, text, notes, corruption_level
            style: 游戏化风格

        Returns:
            批量黑化结果
        """
        system_prompt = _build_corruption_prompt(style)

        # 构建任务列表
        task_list = []
        for i, task in enumerate(tasks, 1):
            task_list.append(
                f"{i}. [ID: {task['id'][:8]}] {task['text']}"
            )

        user_content = f"""需要黑化的任务列表（已过期多日未处理）：
{chr(10).join(task_list)}

请为每个任务生成黑化版本的任务标题，保持原意但带有腐化、堕落的风格。"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        result = await self.chat_completion_json(
            messages=messages,
            response_model=BatchCorruptionResult,
            temperature=0.8,
        )

        logger.info(f"Batch corruption completed for {len(result.tasks)} tasks")
        return result

    async def refine_task_field(
        self,
        task_text: str,
        field_type: str,
        context: str,
        existing_notes: Optional[str] = None,
        existing_checklist: Optional[List[str]] = None,
        style: str = "normal",
    ) -> "RefineFieldResult":
        """
        优化任务的特定字段

        Args:
            task_text: 任务标题
            field_type: 要优化的字段类型 (title, notes, checklist)
            context: 用户提供的额外上下文信息
            existing_notes: 现有的任务备注
            existing_checklist: 现有的子任务列表
            style: 游戏化风格

        Returns:
            优化结果
        """
        system_prompt = _build_refine_prompt(style, field_type)

        user_content = f"任务标题: {task_text}\n\n用户提供的额外信息: {context}"

        if field_type == "notes" and existing_notes:
            user_content += f"\n\n现有备注: {existing_notes}"
        elif field_type == "checklist" and existing_checklist:
            user_content += f"\n\n现有子任务:\n" + "\n".join(f"- {item}" for item in existing_checklist)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        result = await self.chat_completion_json(
            messages=messages,
            response_model=RefineFieldResult,
            temperature=0.7,
        )

        logger.info(f"Field refined: {field_type} for task: {task_text[:30]}...")
        return result


# ============================================
# 数据模型
# ============================================


class ChapterItem(BaseModel):
    """章节项 (V2 阶段化拆解)"""

    chapter_title: str = Field(..., description="章节标题，如'侦察现场'、'收集卷轴'")
    chapter_number: int = Field(1, description="章节序号")
    items: List["ChecklistSuggestion"] = Field(
        default_factory=list,
        description="章节内的子任务列表"
    )


class ChecklistSuggestion(BaseModel):
    """子任务建议"""

    text: str
    priority: str = "medium"  # trivial, easy, medium, hard
    chapter_id: Optional[int] = Field(
        None,
        description="所属章节 ID（用于章节化拆解）"
    )


class SmartDecomposeResult(BaseModel):
    """智能拆解结果 (V2)

    V2 阶段五简化：
    - 使用 Tags 存储游戏化信息
    - 移除元数据相关字段

    核心字段：
    - quest_title: 游戏化后的标题
    - archetype: 任务原型
    - location: 任务地点
    - is_legendary: 是否为传奇任务
    - chapters: 章节化拆解
    - image_ids: 选择的图片 ID 列表
    """

    # 标题
    quest_title: Optional[str] = Field(
        None,
        description="游戏名，游戏化后的标题"
    )
    archetype: Optional[str] = Field(
        None,
        description="任务原型: cleanup/repair/explore/craft/communicate/learn/battle/supply"
    )

    # 游戏化字段
    location: Optional[str] = Field(
        None,
        description="任务地点（游戏化后的地点名）"
    )
    is_legendary: bool = Field(
        False,
        description="是否为传奇任务（复杂任务自动标记）"
    )
    quest_type: Optional[str] = Field(
        None,
        description="任务类型: main(主线)/side(支线)/legendary(传奇)"
    )
    legendary_type: Optional[str] = Field(
        None,
        description="传奇任务具体类型: main/expedition/campaign/escort/saga/chain"
    )

    # 任务链支持
    chain_name: Optional[str] = Field(
        None,
        description="所属任务链名称（用于系列任务）"
    )
    chain_index: Optional[int] = Field(
        None,
        description="在任务链中的序号"
    )

    # 章节化拆解
    chapters: List[ChapterItem] = Field(
        default_factory=list,
        description="章节化拆解（用于复杂任务）"
    )

    # 图片选择
    image_ids: List[str] = Field(
        default_factory=list,
        description="选择的图片 ID 列表（从 images.yaml 中选择）"
    )

    # 原有字段
    task_title: str = Field(
        ...,
        description="最终使用的任务标题"
    )
    task_notes: Optional[str] = None
    suggested_priority: str = "easy"
    checklist: List[ChecklistSuggestion] = []

    def model_post_init(self, __context):
        """后处理：确保 task_title 正确，合并章节子任务"""
        # 使用 quest_title 作为 task_title
        if self.quest_title:
            self.task_title = self.quest_title

        # 如果有章节化拆解，将所有子任务合并到 checklist
        if self.chapters and not self.checklist:
            for chapter in self.chapters:
                for item in chapter.items:
                    item.chapter_id = chapter.chapter_number
                    self.checklist.append(item)


class TitleGenerationResult(BaseModel):
    """称号生成结果"""

    title_name: str
    title_description: Optional[str] = None
    series: Optional[str] = None  # 称号系列（如"星辰系列"、"深渊系列"）


class CorruptionTaskItem(BaseModel):
    """腐烂任务项"""

    task_id: str
    original_text: str
    corrupted_text: str
    corruption_level: int = 1  # 腐烂等级 1-3


class BatchCorruptionResult(BaseModel):
    """批量黑化结果"""

    tasks: List[CorruptionTaskItem] = []


class RefineFieldResult(BaseModel):
    """字段优化结果"""

    field_type: str  # title, notes, checklist
    original_value: Optional[str] = None
    refined_value: str
    explanation: Optional[str] = None  # AI 的修改说明
    checklist: Optional[List[ChecklistSuggestion]] = None  # 仅当 field_type=checklist 时使用


# ============================================
# Prompt 模板
# ============================================

# 通用 Prompt 模板（不随风格变化）
_DECOMPOSE_TEMPLATE = """
你的任务是将用户的模糊任务描述转化为游戏化的任务委托书。

## 输出要求
你必须输出一个 JSON 对象，格式如下：
{{
    "quest_title": "游戏名，游戏化后的标题（不超过50字）",
    "archetype": "任务原型（cleanup/repair/explore/craft/communicate/learn/battle/supply）",
    "location": "任务地点（游戏化后的地点名，如'法师塔'、'指挥中心'）",
    "is_legendary": false,
    "quest_type": "任务类型（main/side/legendary，复杂任务标记为 legendary）",
    "task_title": "最终使用的标题（通常与 quest_title 相同）",
    "task_notes": "任务备注（可选，提供额外上下文或建议）",
    "suggested_priority": "建议优先级（trivial/easy/medium/hard）",
    "image_ids": ["图片ID列表（从可用图片中选择，最多2个）"],
    "chapters": [
        {{
            "chapter_number": 1,
            "chapter_title": "章节标题（如'侦察现场'、'收集卷轴'）",
            "items": [
                {{"text": "子任务描述", "priority": "优先级"}}
            ]
        }}
    ],
    "checklist": []  // 如果使用 chapters，这里留空
}}

## 委托书设计原则
1. **地点感**：根据任务上下文分配合适的游戏化地点
2. **章节化**：复杂任务拆分为 2-5 个章节，每章有明确目标
3. **传奇标记**：超过 5 个子任务或需要多日完成的任务标记为 legendary
4. **图片选择**：从可用图片中选择合适的图片，增强视觉效果

## 任务原型说明
根据任务性质选择最合适的原型：
- cleanup（清理）: 清洁、整理、删除、清理
- repair（修复）: 修理、修正、解决、修复
- explore（探索）: 调研、搜索、发现、探索
- craft（制作）: 创建、编写、设计、制作
- communicate（沟通）: 联系、回复、协调、沟通
- learn（学习）: 研究、阅读、练习、学习
- battle（战斗）: 对抗、挑战、解决难题
- supply（补给）: 购买、准备、补充、补给

## 任务类型说明
- main（主线）: 重要且紧急的任务
- side（支线）: 可以稍后处理的任务
- legendary（传奇）: 复杂、需要多步完成的史诗级任务

## 游戏化约束
1. 游戏名不超过 50 个字符
2. 不要过度浮夸，保持任务的可执行性
3. 如果风格是 normal，quest_title 可以与原标题相同
4. 地点名称要与风格匹配

## 章节化原则
1. 复杂任务（3+ 子任务）优先使用章节化
2. 每章 2-4 个子任务
3. 章节标题要有推进感（准备→执行→完成）
4. 简单任务（1-2 个子任务）可以不使用章节

## 分解原则
1. 子任务应该具体、可操作、有明确的完成标准
2. 子任务之间应该有逻辑顺序，从简单到复杂
3. 每个子任务应该能在 30 分钟内完成
4. 复杂任务分解为 3-7 个子任务，简单任务可以没有子任务
5. 如果用户提供了现有子任务，在保留有价值内容的基础上进行优化

## 优先级说明
- trivial: 非常简单，几分钟就能完成
- easy: 简单，需要少量时间
- medium: 中等难度，需要一些思考
- hard: 困难，需要大量时间或专业技能

请记住：你的目标是生成一张完整的任务委托书，让用户一眼就能了解任务的全貌！"""

_TITLE_TEMPLATE = """
你的任务是根据用户完成的任务内容，生成一个独特的、有意义的称号。

## 输出要求
你必须输出一个 JSON 对象，格式如下：
{{
    "title_name": "称号名称（简洁有力，2-6个字）",
    "title_description": "称号的简短描述或来源（可选，说明为什么这个称号与任务相关）",
    "series": "称号所属系列（可选，如"星辰系列"、"深渊系列"等）"
}}

## 设计原则
1. 称号名称要简洁有力，容易记忆
2. 称号要与任务内容有某种联系，体现成就感
3. 如果用户已有称号，考虑生成进阶称号或新系列的称号
4. 称号应该让用户感到自豪和兴奋
5. 使用你擅长的风格来设计称号，增加游戏化体验

## 进阶规则
- 如果用户已有某系列的称号，可以生成该系列的更高级称号
- 例如：已有"数据猎手"，可生成"高级数据猎手"或"首席数据猎手"
- 也可以完全创新，开启新的称号系列
- 称号的稀有感和成就感比数量更重要

请记住：你的目标是让用户对获得称号感到兴奋，增加游戏的趣味性和动力！"""

_CORRUPTION_TEMPLATE = """
你的任务是将用户过期的任务进行"黑化"处理，让任务标题带有腐化、堕落的风格，以产生紧迫感和行动动力。

## 输出要求
你必须输出一个 JSON 对象，格式如下：
{{
    "tasks": [
        {{
            "task_id": "原任务的 ID",
            "original_text": "原任务标题",
            "corrupted_text": "黑化后的任务标题",
            "corruption_level": 1
        }}
    ]
}}

## 黑化原则
1. 保持原任务的核心意图，不要改变任务的本质
2. 添加腐化、堕落、紧迫的元素，让用户感到必须立即处理
3. 黑化后的标题应该比原标题更有戏剧性和冲击力
4. 使用你擅长的风格来黑化，增加游戏化体验
5. corruption_level 表示腐烂等级（1-3），1为轻度腐化，3为严重腐化

## 注意事项
- 不要让任务变得令人沮丧，而是产生"必须解决"的紧迫感
- 黑化应该有趣且富有戏剧性
- 保持任务的独特性，不要所有任务都用相同的黑化模式

请记住：你的目标是通过戏剧化的黑化，激励用户尽快处理过期任务！"""

_REFINE_TEMPLATES = {
    "title": """
用户希望优化任务标题。你需要根据用户提供的额外信息，生成一个更准确、更具体的任务标题。

## 输出要求
请以 JSON 格式输出结果：
```json
{
    "field_type": "title",
    "original_value": "原标题",
    "refined_value": "优化后的标题",
    "explanation": "简要说明修改原因（可选）"
}
```

## 优化原则
1. 保持任务的核心意图
2. 根据用户提供的上下文信息，让标题更具体、更有指导性
3. 标题应该简洁有力，不超过 50 个字符""",

    "notes": """
用户希望优化任务备注。你需要根据用户提供的额外信息，生成有用的任务备注。

## 输出要求
请以 JSON 格式输出结果：
```json
{
    "field_type": "notes",
    "original_value": "原备注（如有）",
    "refined_value": "优化后的备注",
    "explanation": "简要说明修改原因（可选）"
}
```

## 优化原则
1. 备注应该提供有用的背景信息、上下文或执行建议
2. 根据用户提供的额外信息，补充相关的细节
3. 备注可以包含相关链接、工具、方法等实用信息""",

    "checklist": """
用户希望优化任务的子任务列表。你需要根据用户提供的额外信息，重新生成更合适的子任务。

## 输出要求
请以 JSON 格式输出结果：
```json
{
    "field_type": "checklist",
    "original_value": "原有子任务概要",
    "refined_value": "优化说明",
    "explanation": "简要说明修改原因",
    "checklist": [
        {"text": "子任务描述", "priority": "优先级"}
    ]
}
```

## 优化原则
1. 子任务应该具体、可操作，有明确的完成标准
2. 根据用户提供的上下文信息，调整子任务的具体内容
3. 每个子任务应该能在 30 分钟内完成
4. 复杂任务分解为 3-7 个子任务""",
}


def _build_decompose_prompt(style: str, task_type: str = "todo") -> str:
    """构建拆解任务的 System Prompt (V2)

    V2 新增：
    - 任务类型专属规则
    - 双名结构指导
    - 可用图片信息

    Args:
        style: 游戏化风格
        task_type: 任务类型 (habit/daily/todo)

    Returns:
        完整的 System Prompt
    """
    from habitica_forge.quest import get_task_type_config, get_game_terminology
    from habitica_forge.styles import get_style_config, get_ai_visible_images

    style_config = get_style_config(style)
    style_intro = style_config.prompts.decompose

    # 获取任务类型特定规则
    type_config = get_task_type_config(task_type)
    type_rules = f"""

## 任务类型特定规则 ({type_config.display_name})
核心概念：{type_config.core_concept}
常用术语：{', '.join(type_config.game_terminology[:5])}
默认语气：{type_config.tone}"""

    # 获取可用图片信息
    available_images = get_ai_visible_images(style)
    images_info = ""
    if available_images:
        images_info = f"""

## 可用图片资源
以下图片可供选择（只返回 ID）：
{chr(10).join(f'- {img["id"]}: {img["title"]} - {img["description"]}' for img in available_images[:10])}"""

    return f"{style_intro}\n{_DECOMPOSE_TEMPLATE}\n{type_rules}\n{images_info}"


def _build_title_prompt(style: str) -> str:
    """构建称号生成的 System Prompt"""
    style_config = get_style_config(style)
    style_intro = style_config.prompts.title
    return f"{style_intro}\n{_TITLE_TEMPLATE}"


def _build_corruption_prompt(style: str) -> str:
    """构建任务黑化的 System Prompt"""
    style_config = get_style_config(style)
    style_intro = style_config.prompts.corruption
    return f"{style_intro}\n{_CORRUPTION_TEMPLATE}"


def _build_refine_prompt(style: str, field_type: str) -> str:
    """构建字段优化的 System Prompt"""
    style_config = get_style_config(style)
    style_intro = style_config.prompts.get_refine(field_type)
    field_template = _REFINE_TEMPLATES.get(field_type, _REFINE_TEMPLATES["title"])
    return f"{style_intro}\n{field_template}\n\n请记住：根据用户的额外信息，生成更符合其实际需求的任务内容！"""


# 全局客户端实例（延迟初始化）
_client_instance: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取全局 LLM 客户端实例"""
    global _client_instance
    if _client_instance is None:
        _client_instance = LLMClient()
    return _client_instance
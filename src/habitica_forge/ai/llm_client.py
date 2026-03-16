"""LLM 客户端: 封装 OpenAI 兼容协议"""

import asyncio
import json
from typing import Any, Dict, List, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel

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
    ) -> "SmartDecomposeResult":
        """
        智能拆解任务

        Args:
            task_text: 任务内容
            style: 游戏化风格
            existing_checklist: 现有的 checklist 项（用于更新场景）

        Returns:
            拆解结果
        """
        system_prompt = _build_decompose_prompt(style)

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

        logger.info(f"Smart decompose completed for: {task_text[:50]}...")
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


class ChecklistSuggestion(BaseModel):
    """子任务建议"""

    text: str
    priority: str = "medium"  # trivial, easy, medium, hard


class SmartDecomposeResult(BaseModel):
    """智能拆解结果"""

    task_title: str
    task_notes: Optional[str] = None
    suggested_priority: str = "easy"
    checklist: List[ChecklistSuggestion] = []


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
你的任务是将用户的模糊任务描述分解为清晰、可执行的子任务步骤。

## 输出要求
你必须输出一个 JSON 对象，格式如下：
{{
    "task_title": "优化后的任务标题（简短有力，保留原意）",
    "task_notes": "任务备注（可选，提供额外上下文或建议）",
    "suggested_priority": "建议优先级（trivial/easy/medium/hard）",
    "checklist": [
        {{
            "text": "子任务描述",
            "priority": "子任务优先级（trivial/easy/medium/hard）"
        }}
    ]
}}

## 分解原则
1. 子任务应该具体、可操作、有明确的完成标准
2. 子任务之间应该有逻辑顺序，从简单到复杂
3. 每个子任务应该能在 30 分钟内完成
4. 复杂任务分解为 3-7 个子任务，简单任务可以没有子任务
5. 如果用户提供了现有子任务，在保留有价值内容的基础上进行优化
6. 使用你擅长的风格来描述子任务，让任务更有趣味性

## 优先级说明
- trivial: 非常简单，几分钟就能完成
- easy: 简单，需要少量时间
- medium: 中等难度，需要一些思考
- hard: 困难，需要大量时间或专业技能

请记住：你的目标是帮助用户把模糊焦虑转化为清晰可执行的步骤，同时用有趣的语言风格增加动力！"""

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


def _build_decompose_prompt(style: str) -> str:
    """构建拆解任务的 System Prompt"""
    style_config = get_style_config(style)
    style_intro = style_config.prompts.decompose
    return f"{style_intro}\n{_DECOMPOSE_TEMPLATE}"


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
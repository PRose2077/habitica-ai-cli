"""配置中心: 使用 pydantic-settings 管理配置"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置模型"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    # ============================================
    # Habitica 认证（必填）
    # ============================================
    habitica_user_id: str = Field(
        ...,
        description="Habitica 用户 ID",
        alias="HABITICA_USER_ID",
    )
    habitica_api_token: str = Field(
        ...,
        description="Habitica API Token",
        alias="HABITICA_API_TOKEN",
    )

    # ============================================
    # LLM 引擎认证（必填）
    # ============================================
    llm_api_key: str = Field(
        ...,
        description="LLM API Key",
        alias="LLM_API_KEY",
    )
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="LLM API Base URL",
        alias="LLM_BASE_URL",
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        description="LLM 模型名称",
        alias="LLM_MODEL",
    )

    # ============================================
    # 称号掉落权重与算法
    # ============================================
    weight_todo: float = Field(
        default=1.0,
        ge=0.0,
        le=10.0,
        description="TODO 任务权重系数",
        alias="WEIGHT_TODO",
    )
    weight_daily: float = Field(
        default=0.3,
        ge=0.0,
        le=10.0,
        description="DAILY 任务权重系数",
        alias="WEIGHT_DAILY",
    )
    daily_streak_bonus: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description="连击加成系数",
        alias="DAILY_STREAK_BONUS",
    )
    title_threshold: float = Field(
        default=8.5,
        ge=0.0,
        le=20.0,
        description="触发称号掉落的阈值",
        alias="TITLE_THRESHOLD",
    )

    # ============================================
    # 系统行为
    # ============================================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="WARNING",
        description="日志级别",
        alias="LOG_LEVEL",
    )
    scan_interval_hours: int = Field(
        default=12,
        ge=1,
        le=168,
        description="腐烂扫描间隔（小时）",
        alias="SCAN_INTERVAL_HOURS",
    )
    forge_style: str = Field(
        default="Cyberpunk",
        description="游戏化风格（Cyberpunk, Wuxia, Fantasy...）",
        alias="FORGE_STYLE",
    )

    @field_validator("habitica_user_id", "habitica_api_token", "llm_api_key")
    @classmethod
    def validate_required_fields(cls, v: str, info) -> str:
        """验证必填字段不为空"""
        if not v or v.strip() == "":
            raise ValueError(f"{info.field_name} 是必填字段，不能为空")
        return v.strip()

    @property
    def habitica_headers(self) -> dict[str, str]:
        """获取 Habitica API 请求头"""
        return {
            "x-api-user": self.habitica_user_id,
            "x-api-key": self.habitica_api_token,
            "x-client": f"habitica-forge-{__import__('habitica_forge', fromlist=['__version__']).__version__}",
        }

    @property
    def llm_headers(self) -> dict[str, str]:
        """获取 LLM API 请求头"""
        return {
            "Authorization": f"Bearer {self.llm_api_key}",
            "Content-Type": "application/json",
        }


@lru_cache
def get_settings() -> Settings:
    """获取配置单例（缓存）"""
    return Settings()


# 便捷访问
settings = get_settings()
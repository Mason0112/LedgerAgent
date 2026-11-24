"""LLM Provider 工廠函式：依設定或請求參數動態建立對應的 AI 模型供應商。"""

from __future__ import annotations

from ledger_agent.config import Settings
from ledger_agent.providers.base import BaseLLMProvider
from ledger_agent.providers.gemini import GeminiProvider
from ledger_agent.providers.mock import MockLLMProvider
from ledger_agent.providers.openai_provider import OpenAIProvider


def create_llm_provider(
    settings: Settings,
    provider_override: str | None = None,
) -> BaseLLMProvider:
    """根據設定檔或 API 傳入的 provider 名稱建立模型實例。"""
    provider_name = (provider_override or settings.llm_provider).strip().lower()

    if provider_name == "mock":
        return MockLLMProvider()

    if provider_name == "gemini":
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model_name=settings.gemini_model,
        )

    if provider_name == "openai":
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model_name=settings.openai_model,
            base_url=settings.openai_base_url,
        )

    raise ValueError(
        f"不支援的 LLM_PROVIDER: {provider_name}（請使用 mock、gemini 或 openai）"
    )

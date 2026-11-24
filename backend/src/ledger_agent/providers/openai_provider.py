"""OpenAI / OpenAI-Compatible 模型實作（同時支援 GPT-4o 與 Ollama / OpenRouter）。"""

from __future__ import annotations

import base64

from openai import OpenAI

from ledger_agent.models.journal import JournalEntryDraft
from ledger_agent.models.skill import CompanySkill, HistoryExample, VendorRule
from ledger_agent.models.voucher import VoucherExtraction
from ledger_agent.providers.base import BaseLLMProvider
from ledger_agent.providers.gemini import OCR_EXTRACTION_PROMPT


class OpenAIProvider(BaseLLMProvider):
    """透過 OpenAI Structured Outputs 解析憑證與生成分錄。"""

    provider_name = "openai"

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o-mini",
        base_url: str = "",
    ) -> None:
        if not api_key and not base_url:
            raise ValueError("使用 OpenAIProvider 必須設定 OPENAI_API_KEY 或 OPENAI_BASE_URL")
        self.client = OpenAI(
            api_key=api_key or "ollama",
            base_url=base_url or None,
        )
        self.model_name = model_name

    def extract_voucher(
        self,
        file_bytes: bytes,
        mime_type: str,
        filename: str,
    ) -> VoucherExtraction:
        b64_data = base64.b64encode(file_bytes).decode("utf-8")
        data_uri = f"data:{mime_type};base64,{b64_data}"

        completion = self.client.beta.chat.completions.parse(
            model=self.model_name,
            temperature=0.0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": OCR_EXTRACTION_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
            response_format=VoucherExtraction,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI 未回傳有效的 VoucherExtraction 結構化內容")
        return parsed

    def generate_journal_entry(
        self,
        voucher: VoucherExtraction,
        skill: CompanySkill,
        matched_rules: list[VendorRule],
        history_examples: list[HistoryExample],
        system_prompt: str,
        user_prompt: str,
    ) -> JournalEntryDraft:
        completion = self.client.beta.chat.completions.parse(
            model=self.model_name,
            temperature=0.1,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=JournalEntryDraft,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI 未回傳有效的 JournalEntryDraft 結構化內容")
        return parsed

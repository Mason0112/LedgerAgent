"""AI 模型供應商抽象基底類別。

Python 學習重點：
- `ABC` (Abstract Base Class) + `@abstractmethod` 定義統一介面。
- 只要新增一個繼承 `BaseLLMProvider` 的類別，就能無痛切換 Gemini / OpenAI / Ollama / Claude。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ledger_agent.models.journal import JournalEntryDraft
from ledger_agent.models.skill import CompanySkill, HistoryExample, VendorRule
from ledger_agent.models.voucher import VoucherExtraction


class BaseLLMProvider(ABC):
    """所有多模態 OCR 與分錄生成模型的統一介面。"""

    provider_name: str = "base"
    model_name: str = "unknown"

    @abstractmethod
    def extract_voucher(
        self,
        file_bytes: bytes,
        mime_type: str,
        filename: str,
    ) -> VoucherExtraction:
        """Stage 1: 從圖片或 PDF 憑證解析出標準 VoucherExtraction JSON。"""

    @abstractmethod
    def generate_journal_entry(
        self,
        voucher: VoucherExtraction,
        skill: CompanySkill,
        matched_rules: list[VendorRule],
        history_examples: list[HistoryExample],
        system_prompt: str,
        user_prompt: str,
    ) -> JournalEntryDraft:
        """Stage 3: 根據憑證資料與公司 Skill 產出結構化分錄草稿 JSON。"""

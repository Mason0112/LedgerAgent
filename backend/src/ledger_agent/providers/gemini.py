"""Google Gemini 多模態模型實作（使用官方 google-genai SDK）。"""

from __future__ import annotations

from google import genai
from google.genai import types

from ledger_agent.models.journal import JournalEntryDraft
from ledger_agent.models.skill import CompanySkill, HistoryExample, VendorRule
from ledger_agent.models.voucher import VoucherExtraction
from ledger_agent.providers.base import BaseLLMProvider


OCR_EXTRACTION_PROMPT = """你是一位專業的台灣會計憑證辨識專家。
請仔細閱讀這張憑證（可能是三聯式發票、二聯式發票、電子發票證明聯或收據），並精確萃取出結構化欄位。

注意事項：
1. 若憑證日期為民國年（例如 115/03/15），請務必換算為西元年 YYYY-MM-DD（民國年 + 1911，例如 2026-03-15）。
2. 發票號碼請保留字軌與連字號（例如 AB-12345678）。
3. 若為電子發票證明聯或二聯式發票僅印出含稅總計，未稅與稅額欄位可填 null（由後續會計引擎推算），切勿捏造憑證上不存在的統編。
4. 辨識所有可見品項明細與備註/手寫用途。
"""


class GeminiProvider(BaseLLMProvider):
    """透過 Google Gemini 原生多模態 Structured Output 解析憑證與生成分錄。"""

    provider_name = "gemini"

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash") -> None:
        if not api_key:
            raise ValueError("使用 GeminiProvider 必須設定 GEMINI_API_KEY")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def extract_voucher(
        self,
        file_bytes: bytes,
        mime_type: str,
        filename: str,
    ) -> VoucherExtraction:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                OCR_EXTRACTION_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=VoucherExtraction,
                temperature=0.0,
            ),
        )
        return VoucherExtraction.model_validate_json(response.text)

    def generate_journal_entry(
        self,
        voucher: VoucherExtraction,
        skill: CompanySkill,
        matched_rules: list[VendorRule],
        history_examples: list[HistoryExample],
        system_prompt: str,
        user_prompt: str,
    ) -> JournalEntryDraft:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=JournalEntryDraft,
                temperature=0.1,
            ),
        )
        return JournalEntryDraft.model_validate_json(response.text)

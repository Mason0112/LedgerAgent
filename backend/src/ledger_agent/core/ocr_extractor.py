"""Stage 1: 多模態憑證解析器。"""

from __future__ import annotations

import mimetypes
from pathlib import Path

from ledger_agent.models.voucher import VoucherExtraction
from ledger_agent.providers.base import BaseLLMProvider


SUPPORTED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}


class VoucherOCRExtractor:
    """負責驗證檔案類型並交由多模態 VLM 解析出標準 VoucherExtraction JSON。"""

    def __init__(self, provider: BaseLLMProvider) -> None:
        self.provider = provider

    def extract_from_bytes(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str | None = None,
    ) -> VoucherExtraction:
        resolved_mime = mime_type or self._guess_mime_type(filename)
        if resolved_mime not in SUPPORTED_MIME_TYPES:
            raise ValueError(
                f"不支援的憑證檔案格式：{resolved_mime}（支援 JPG / PNG / WEBP / PDF）"
            )
        return self.provider.extract_voucher(
            file_bytes=file_bytes,
            mime_type=resolved_mime,
            filename=filename,
        )

    @staticmethod
    def _guess_mime_type(filename: str) -> str:
        guessed, _ = mimetypes.guess_type(filename)
        if guessed:
            return guessed
        suffix = Path(filename).suffix.lower()
        mapping = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
            ".pdf": "application/pdf",
        }
        return mapping.get(suffix, "application/octet-stream")

"""分錄草稿、會計檢核問題與 API 回應資料模型。"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from ledger_agent.models.voucher import VoucherExtraction


class EntrySide(str, Enum):
    """分錄借貸方向。"""

    DEBIT = "debit"
    CREDIT = "credit"


class ValidationSeverity(str, Enum):
    """程式化會計檢核的嚴重度。"""

    ERROR = "error"  # 必須修正（例如借貸不平、科目不存在）
    WARNING = "warning"  # 提醒人工確認（例如買方統編不符、重複發票）


class JournalLine(BaseModel):
    """單一借方或貸方分錄明細。"""

    side: EntrySide = Field(..., description="借方 (debit) 或 貸方 (credit)")
    account_code: str = Field(..., description="會計科目代碼（必須存在於公司科目表）")
    account_name: str = Field(..., description="會計科目名稱")
    amount: Decimal = Field(..., ge=Decimal("0"), description="金額（正數）")
    memo: str = Field(default="", description="分錄摘要")


class JournalEntryDraft(BaseModel):
    """Stage 3 AI 產出的結構化分錄草稿 JSON。"""

    entry_date: str = Field(..., description="傳票日期 (YYYY-MM-DD)")
    summary: str = Field(..., description="傳票總摘要")
    vat_deductible: bool = Field(
        default=False,
        description="本筆憑證進項稅額是否可扣抵",
    )
    lines: list[JournalLine] = Field(..., min_length=2, description="借貸分錄明細")
    applied_rules: list[str] = Field(
        default_factory=list,
        description="本次判斷引用了哪些 SKILL.md 條款、vendor_rules 或歷史範例",
    )
    reasoning: str = Field(..., description="AI 解釋為何如此切分錄的完整推理過程")
    confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="分錄信心分數")


class ValidationIssue(BaseModel):
    """Stage 4 程式化會計檢核引擎回報的異常項目。"""

    code: str = Field(..., description="錯誤代碼，如 UNBALANCED_ENTRY")
    severity: ValidationSeverity
    message: str


class JournalRunResponse(BaseModel):
    """單次分錄生成執行結果（便於修改 Skill 後對照歷次 JSON 差異）。"""

    run_id: str
    voucher_id: str
    company_id: str
    provider: str
    model_name: str
    status: str  # draft | needs_review | approved
    skill_hash: str
    matched_rule_ids: list[str] = Field(default_factory=list)
    retrieved_example_ids: list[str] = Field(default_factory=list)
    journal_draft: dict[str, Any]
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    is_valid: bool = True
    created_at: datetime


class VoucherSummaryResponse(BaseModel):
    """憑證列表精簡回應。"""

    voucher_id: str
    company_id: str
    filename: str | None = None
    vendor_name: str
    voucher_number: str | None = None
    voucher_date: str | None = None
    total_amount: str
    latest_status: str
    runs_count: int
    created_at: datetime


class VoucherDetailResponse(BaseModel):
    """憑證完整詳情（含 OCR JSON 與歷次分錄 Run 快照）。"""

    voucher_id: str
    company_id: str
    filename: str | None = None
    file_url: str | None = None
    extraction: VoucherExtraction
    runs: list[JournalRunResponse] = Field(default_factory=list)
    created_at: datetime

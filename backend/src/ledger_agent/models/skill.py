"""每間公司客製化 Skills 與會計科目表資料模型。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
    """對應 companies/<company_id>/company.yaml。"""

    company_id: str
    name: str
    tax_id: str = ""
    industry: str = ""
    currency: str = "TWD"
    vat_rate: Decimal = Decimal("0.05")
    default_payment_account: str = "1112"
    capitalization_threshold: Decimal = Decimal("80000")
    description: str = ""


class AccountItem(BaseModel):
    """單一會計科目定義（對應 chart_of_accounts.yaml）。"""

    code: str
    name: str
    category: str  # asset | liability | equity | revenue | cost | expense
    normal_side: str  # debit | credit
    description: str = ""


class VendorRule(BaseModel):
    """針對特定廠商或關鍵字的確定性對應規則（對應 vendor_rules.yaml）。"""

    rule_id: str
    match_vendor_tax_id: str = ""
    match_keywords: list[str] = Field(default_factory=list)
    debit_account_code: str
    credit_account_code: str | None = None
    vat_deductible: bool = True
    note: str = ""


class HistoryExample(BaseModel):
    """已核准的歷史分錄範例（對應 history.jsonl 的每一行）。"""

    example_id: str
    vendor_name: str
    vendor_tax_id: str | None = None
    voucher_type: str = "electronic_invoice"
    items_summary: str = ""
    total_amount: str
    entries: list[dict[str, Any]] = Field(default_factory=list)
    reasoning: str = ""


class CompanySkill(BaseModel):
    """完整載入後的單一公司 Skill 套件。"""

    profile: CompanyProfile
    skill_markdown: str
    chart_of_accounts: list[AccountItem]
    vendor_rules: list[VendorRule] = Field(default_factory=list)
    history_examples: list[HistoryExample] = Field(default_factory=list)

    def account_map(self) -> dict[str, AccountItem]:
        """建立 {科目代碼: AccountItem} 字典，方便 O(1) 快速查詢。"""
        return {acc.code: acc for acc in self.chart_of_accounts}

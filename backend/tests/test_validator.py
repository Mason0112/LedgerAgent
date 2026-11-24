"""測試 Stage 4 程式化會計硬規則檢核器 (AccountingValidator)。"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ledger_agent.core.validator import AccountingValidator
from ledger_agent.models.journal import (
    EntrySide,
    JournalEntryDraft,
    JournalLine,
    ValidationSeverity,
)
from ledger_agent.models.voucher import VoucherExtraction, VoucherType
from ledger_agent.skills.loader import SkillLoader


def test_validator_catches_unbalanced_and_invalid_account(temp_companies_dir: Path) -> None:
    skill = SkillLoader(temp_companies_dir).load("demo_tech_co")
    voucher = VoucherExtraction(
        voucher_type=VoucherType.ELECTRONIC_INVOICE,
        voucher_number="ZZ-11112222",
        vendor_name="測試廠商",
        buyer_tax_id="99999999",  # 故意填錯買方統編
        subtotal=Decimal("1000"),
        tax_amount=Decimal("50"),
        total_amount=Decimal("1050"),
    )
    bad_draft = JournalEntryDraft(
        entry_date="2026-11-24",
        summary="故意不平衡且科目錯誤的分錄",
        vat_deductible=False,
        lines=[
            JournalLine(
                side=EntrySide.DEBIT,
                account_code="9999",  # 不存在於科目表
                account_name="虛構科目",
                amount=Decimal("1000"),
            ),
            JournalLine(
                side=EntrySide.CREDIT,
                account_code="1112",
                account_name="零用金",
                amount=Decimal("1050"),  # 與借方不平衡
            ),
        ],
        reasoning="測試用錯誤分錄",
    )

    issues = AccountingValidator.validate(
        voucher=voucher,
        draft=bad_draft,
        skill=skill,
        existing_voucher_numbers={"ZZ-11112222"},
    )
    codes = {i.code for i in issues}

    assert "UNBALANCED_ENTRY" in codes
    assert "INVALID_ACCOUNT_CODE" in codes
    assert "BUYER_TAX_ID_MISMATCH" in codes
    assert "DUPLICATE_VOUCHER_NUMBER" in codes
    assert AccountingValidator.has_errors(issues) is True


def test_validator_passes_clean_entry(temp_companies_dir: Path) -> None:
    skill = SkillLoader(temp_companies_dir).load("demo_tech_co")
    voucher = VoucherExtraction(
        voucher_type=VoucherType.TRIPLICATE_INVOICE,
        voucher_number="AA-00001111",
        vendor_name="原價屋電腦有限公司",
        buyer_tax_id="83124567",
        subtotal=Decimal("20000"),
        tax_amount=Decimal("1000"),
        total_amount=Decimal("21000"),
    )
    good_draft = JournalEntryDraft(
        entry_date="2026-11-24",
        summary="採購螢幕",
        vat_deductible=True,
        lines=[
            JournalLine(
                side=EntrySide.DEBIT,
                account_code="6116",
                account_name="雜項購置",
                amount=Decimal("20000"),
            ),
            JournalLine(
                side=EntrySide.DEBIT,
                account_code="1261",
                account_name="進項稅額",
                amount=Decimal("1000"),
            ),
            JournalLine(
                side=EntrySide.CREDIT,
                account_code="1112",
                account_name="零用金",
                amount=Decimal("21000"),
            ),
        ],
        reasoning="合法平衡分錄",
    )

    issues = AccountingValidator.validate(voucher=voucher, draft=good_draft, skill=skill)
    assert issues == []
    assert not any(i.severity == ValidationSeverity.ERROR for i in issues)

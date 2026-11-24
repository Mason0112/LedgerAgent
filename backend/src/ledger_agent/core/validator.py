"""Stage 4: 程式化會計硬規則檢核引擎 (Accounting Guardrails)。

設計原則：
「AI 擅長語意理解與分類，程式擅長精準算術與合規檢核。」
所有金額計算全面使用 `Decimal`，避免浮點數誤差。
"""

from __future__ import annotations

from decimal import Decimal

from ledger_agent.models.journal import (
    EntrySide,
    JournalEntryDraft,
    ValidationIssue,
    ValidationSeverity,
)
from ledger_agent.models.skill import CompanySkill
from ledger_agent.models.voucher import VoucherExtraction, VoucherType


class AccountingValidator:
    """對 AI 產出的分錄進行五大確定性檢核。"""

    @staticmethod
    def validate(
        voucher: VoucherExtraction,
        draft: JournalEntryDraft,
        skill: CompanySkill,
        existing_voucher_numbers: set[str] | None = None,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        accounts = skill.account_map()

        # 1. 借貸平衡檢查 (ERROR)
        debit_total = sum(
            (line.amount for line in draft.lines if line.side == EntrySide.DEBIT),
            start=Decimal("0"),
        )
        credit_total = sum(
            (line.amount for line in draft.lines if line.side == EntrySide.CREDIT),
            start=Decimal("0"),
        )
        if debit_total != credit_total:
            issues.append(
                ValidationIssue(
                    code="UNBALANCED_ENTRY",
                    severity=ValidationSeverity.ERROR,
                    message=f"借貸不平衡：借方總計 {debit_total} != 貸方總計 {credit_total}",
                )
            )

        if debit_total == Decimal("0"):
            issues.append(
                ValidationIssue(
                    code="ZERO_AMOUNT_ENTRY",
                    severity=ValidationSeverity.ERROR,
                    message="分錄借貸金額為 0，請確認憑證金額是否正確。",
                )
            )

        # 2. 分錄總額與憑證總額一致性檢查 (WARNING)
        if debit_total == credit_total and debit_total != voucher.total_amount:
            issues.append(
                ValidationIssue(
                    code="TOTAL_AMOUNT_MISMATCH",
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"分錄借方合計 ({debit_total}) 與憑證含稅總計 ({voucher.total_amount}) 不一致。"
                    ),
                )
            )

        # 3. 科目表白名單與科目名稱檢查 (ERROR)
        for line in draft.lines:
            if line.account_code not in accounts:
                issues.append(
                    ValidationIssue(
                        code="INVALID_ACCOUNT_CODE",
                        severity=ValidationSeverity.ERROR,
                        message=(
                            f"科目代碼 {line.account_code} ({line.account_name}) 不存在於 "
                            f"{skill.profile.company_id} 的 chart_of_accounts.yaml。"
                        ),
                    )
                )

        # 4. 憑證未稅 + 稅額 = 總計勾稽檢查 (WARNING)
        if voucher.subtotal is not None and voucher.tax_amount is not None:
            if voucher.subtotal + voucher.tax_amount != voucher.total_amount:
                issues.append(
                    ValidationIssue(
                        code="VOUCHER_MATH_MISMATCH",
                        severity=ValidationSeverity.WARNING,
                        message=(
                            f"憑證金額勾稽異常：未稅({voucher.subtotal}) + 稅額({voucher.tax_amount}) "
                            f"!= 總計({voucher.total_amount})。"
                        ),
                    )
                )

        # 5. 收據不應拆出進項稅額檢查 (WARNING)
        has_input_vat_line = any(line.account_code == "1261" for line in draft.lines)
        if voucher.voucher_type == VoucherType.RECEIPT and has_input_vat_line:
            issues.append(
                ValidationIssue(
                    code="RECEIPT_WITH_VAT",
                    severity=ValidationSeverity.WARNING,
                    message="憑證類型為免用統一發票收據，不應切出 1261 進項稅額。",
                )
            )

        # 6. 買方統編核對 (WARNING)
        if (
            voucher.buyer_tax_id
            and skill.profile.tax_id
            and voucher.buyer_tax_id.strip() != skill.profile.tax_id.strip()
        ):
            issues.append(
                ValidationIssue(
                    code="BUYER_TAX_ID_MISMATCH",
                    severity=ValidationSeverity.WARNING,
                    message=(
                        f"憑證買方統編 ({voucher.buyer_tax_id}) 與本公司統編 "
                        f"({skill.profile.tax_id}) 不符，請確認是否為其他公司憑證或個人消費。"
                    ),
                )
            )

        # 7. 重複發票號碼檢查 (WARNING)
        if (
            existing_voucher_numbers
            and voucher.voucher_number
            and voucher.voucher_number.strip() in existing_voucher_numbers
        ):
            issues.append(
                ValidationIssue(
                    code="DUPLICATE_VOUCHER_NUMBER",
                    severity=ValidationSeverity.WARNING,
                    message=f"發票/憑證號碼 {voucher.voucher_number} 已存在於本公司紀錄中，請防範重複入帳。",
                )
            )

        return issues

    @staticmethod
    def has_errors(issues: list[ValidationIssue]) -> bool:
        return any(issue.severity == ValidationSeverity.ERROR for issue in issues)

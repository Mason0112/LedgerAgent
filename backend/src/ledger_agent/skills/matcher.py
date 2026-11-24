"""確定性廠商規則匹配器 (vendor_rules.yaml)。

當憑證的賣方統編或品項關鍵字命中固定規則時，提供明確建議給 AI 與檢核器。
"""

from __future__ import annotations

from ledger_agent.models.skill import VendorRule
from ledger_agent.models.voucher import VoucherExtraction


class VendorRuleMatcher:
    """根據賣方統編與文字關鍵字比對公司 vendor_rules。"""

    @staticmethod
    def match(
        voucher: VoucherExtraction, rules: list[VendorRule]
    ) -> list[VendorRule]:
        """回傳所有命中的規則列表（優先比對統編，其次比對關鍵字）。"""
        searchable_text = " ".join(
            filter(
                None,
                [
                    voucher.vendor_name,
                    voucher.notes or "",
                    " ".join(item.description for item in voucher.items),
                ],
            )
        ).lower()

        matched: list[VendorRule] = []
        for rule in rules:
            # 1. 統編精準比對
            if (
                rule.match_vendor_tax_id
                and voucher.vendor_tax_id
                and rule.match_vendor_tax_id.strip() == voucher.vendor_tax_id.strip()
            ):
                matched.append(rule)
                continue

            # 2. 廠商名稱 / 品項 / 備註關鍵字比對
            if any(
                kw.lower() in searchable_text
                for kw in rule.match_keywords
                if kw.strip()
            ):
                matched.append(rule)

        return matched

"""離線智慧模擬 Provider（不需 API Key，適合開發測試與觀察 Skill 改變對分錄 JSON 的影響）。

設計特色：
- 會實際解析該公司的 `vendor_rules.yaml`、`SKILL.md` 規則與 `history.jsonl`。
- 當你在介面上修改 `SKILL.md`（例如把咖啡對應科目從 `6125` 改成 `6123`，或加上 `星巴克 -> 6299`），
  重跑分錄時 MockProvider 會即時反映新的科目與稅額扣抵規則！
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from ledger_agent.models.journal import EntrySide, JournalEntryDraft, JournalLine
from ledger_agent.models.skill import CompanySkill, HistoryExample, VendorRule
from ledger_agent.models.voucher import (
    PaymentMethod,
    VoucherExtraction,
    VoucherLineItem,
    VoucherType,
)
from ledger_agent.providers.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """不呼叫外部 API 的規則型模擬引擎，用來快速測試完整管線與 Skill 差異。"""

    provider_name = "mock"
    model_name = "mock-skill-interpreter-v1"

    def extract_voucher(
        self,
        file_bytes: bytes,
        mime_type: str,
        filename: str,
    ) -> VoucherExtraction:
        """根據檔名關鍵字回傳擬真的台灣憑證 JSON，方便無 Key 測試上傳流程。"""
        lower_name = filename.lower()
        today = date.today().isoformat()

        if any(k in lower_name for k in ("aws", "gcp", "cloud", "azure")):
            return VoucherExtraction(
                voucher_type=VoucherType.TRIPLICATE_INVOICE,
                voucher_number="CD-44882910",
                voucher_date=today,
                vendor_name="台灣亞馬遜雲端服務有限公司 (AWS)",
                vendor_tax_id="54321987",
                buyer_name="星辰科技股份有限公司",
                buyer_tax_id="83124567",
                currency="TWD",
                subtotal=Decimal("10000"),
                tax_amount=Decimal("500"),
                total_amount=Decimal("10500"),
                payment_method=PaymentMethod.CREDIT_CARD,
                items=[
                    VoucherLineItem(
                        description="AWS EC2 & RDS 雲端伺服器月費",
                        quantity=Decimal("1"),
                        unit_price=Decimal("10000"),
                        amount=Decimal("10000"),
                    )
                ],
                notes="正式環境主機月結費用",
                confidence=0.96,
                raw_text=f"[Mock OCR from {filename}] AWS 雲端月費 NT$10,500",
            )

        if any(k in lower_name for k in ("pc", "mac", "laptop", "equip", "coffee_machine")):
            return VoucherExtraction(
                voucher_type=VoucherType.TRIPLICATE_INVOICE,
                voucher_number="EF-77120394",
                voucher_date=today,
                vendor_name="蘋果商務經銷有限公司",
                vendor_tax_id="28991122",
                buyer_tax_id="83124567",
                currency="TWD",
                subtotal=Decimal("85000"),
                tax_amount=Decimal("4250"),
                total_amount=Decimal("89250"),
                payment_method=PaymentMethod.BANK_TRANSFER,
                items=[
                    VoucherLineItem(
                        description="MacBook Pro 16吋 研發工作站",
                        quantity=Decimal("1"),
                        unit_price=Decimal("85000"),
                        amount=Decimal("85000"),
                    )
                ],
                notes="新進工程師電腦設備採購",
                confidence=0.95,
                raw_text=f"[Mock OCR from {filename}] MacBook Pro 設備採購 NT$89,250",
            )

        # 預設回傳一張最適合拿來比較「科技公司 vs 咖啡公司」差異的星巴克電子發票
        return VoucherExtraction(
            voucher_type=VoucherType.ELECTRONIC_INVOICE,
            voucher_number="AB-88234109",
            voucher_date=today,
            vendor_name="悠旅生活事業股份有限公司(星巴克)",
            vendor_tax_id="16097091",
            buyer_tax_id="83124567",
            currency="TWD",
            subtotal=Decimal("1000"),
            tax_amount=Decimal("50"),
            total_amount=Decimal("1050"),
            payment_method=PaymentMethod.PETTY_CASH,
            items=[
                VoucherLineItem(
                    description="特大杯美式咖啡 x3",
                    quantity=Decimal("3"),
                    unit_price=Decimal("140"),
                    amount=Decimal("420"),
                ),
                VoucherLineItem(
                    description="那堤咖啡 x4",
                    quantity=Decimal("4"),
                    unit_price=Decimal("157.5"),
                    amount=Decimal("630"),
                ),
            ],
            notes="內部會議飲品 / 競品試飲",
            confidence=0.94,
            raw_text=f"[Mock OCR from {filename}] 星巴克電子發票 總計 NT$1,050",
        )

    def generate_journal_entry(
        self,
        voucher: VoucherExtraction,
        skill: CompanySkill,
        matched_rules: list[VendorRule],
        history_examples: list[HistoryExample],
        system_prompt: str,
        user_prompt: str,
    ) -> JournalEntryDraft:
        """解析公司 Skill、廠商規則與歷史記憶，產出結構化借貸分錄。"""
        accounts = skill.account_map()
        text = self._build_searchable_text(voucher)
        applied_rules: list[str] = []
        reasoning_parts: list[str] = []

        debit_code: str | None = None
        credit_code: str = self._pick_credit_account(voucher, skill, accounts)
        vat_deductible: bool = voucher.voucher_type != VoucherType.RECEIPT

        # 1. 優先套用 SKILL.md 內使用者手寫的明確覆寫語法（例如「星巴克 -> 6123」或「咖啡 => 5111」）
        override = self._parse_explicit_skill_override(text, skill.skill_markdown, accounts)
        if override is not None:
            debit_code, override_deductible, matched_line = override
            applied_rules.append(f"SKILL.md 自訂覆寫: {matched_line}")
            reasoning_parts.append(
                f"命中 SKILL.md 自訂規則「{matched_line}」，指定借方科目為 {debit_code}。"
            )
            if override_deductible is not None:
                vat_deductible = override_deductible

        # 2. 次優先：確定性廠商規則 (vendor_rules.yaml)
        if debit_code is None and matched_rules:
            rule = matched_rules[0]
            if rule.debit_account_code in accounts:
                debit_code = rule.debit_account_code
                if rule.credit_account_code and rule.credit_account_code in accounts:
                    credit_code = rule.credit_account_code
                vat_deductible = rule.vat_deductible and (
                    voucher.voucher_type != VoucherType.RECEIPT
                )
                applied_rules.append(f"vendor_rules.yaml: {rule.rule_id}")
                reasoning_parts.append(f"命中廠商規則 {rule.rule_id}（{rule.note}）。")

        # 3. 讀取 SKILL.md 自然語言規則（依關鍵字與該行提到的科目代碼動態解析）
        if debit_code is None:
            skill_match = self._interpret_skill_markdown(voucher, text, skill, accounts)
            if skill_match is not None:
                debit_code, skill_deductible, rule_desc = skill_match
                vat_deductible = skill_deductible and (
                    voucher.voucher_type != VoucherType.RECEIPT
                )
                applied_rules.append(f"SKILL.md: {rule_desc}")
                reasoning_parts.append(f"依 {skill.profile.name} SKILL.md 判斷：{rule_desc}。")

        # 4. 參考歷史核准範例 (history.jsonl)
        if debit_code is None and history_examples:
            ex = history_examples[0]
            for entry in ex.entries:
                if entry.get("side") == "debit" and entry.get("account_code") != "1261":
                    candidate = str(entry.get("account_code"))
                    if candidate in accounts:
                        debit_code = candidate
                        applied_rules.append(f"history.jsonl: {ex.example_id}")
                        reasoning_parts.append(
                            f"參考歷史核准分錄 {ex.example_id}（{ex.vendor_name}），沿用科目 {candidate}。"
                        )
                        break

        # 5. 最終保底科目
        if debit_code is None:
            debit_code = "6299" if "6299" in accounts else next(iter(accounts))
            applied_rules.append("fallback: 其他費用")
            reasoning_parts.append(
                f"未命中特定規則，暫歸保底科目 {debit_code} {accounts[debit_code].name}。"
            )

        # 若科目為交際費(6123)或職工福利(6125)，且 SKILL.md 有提及不可扣抵，強制不拆進項稅額
        if debit_code in {"6123", "6125"} and "不得扣抵" in skill.skill_markdown:
            vat_deductible = False
            reasoning_parts.append(
                f"科目 {debit_code} 依營業稅法與公司 Skill 規定進項稅額不得扣抵，含稅總額直接入帳。"
            )

        # 若該公司沒有 1261 進項稅額科目，也無法拆分
        if "1261" not in accounts:
            vat_deductible = False

        # 組裝借貸分錄（確保嚴格使用 Decimal 並借貸平衡）
        lines = self._build_balanced_lines(
            voucher=voucher,
            debit_code=debit_code,
            credit_code=credit_code,
            vat_deductible=vat_deductible,
            accounts=accounts,
            vat_rate=skill.profile.vat_rate,
        )

        entry_date = voucher.voucher_date or date.today().isoformat()
        items_desc = "、".join(item.description for item in voucher.items[:2]) or voucher.vendor_name
        summary = f"{voucher.vendor_name} - {items_desc}"

        return JournalEntryDraft(
            entry_date=entry_date,
            summary=summary,
            vat_deductible=vat_deductible,
            lines=lines,
            applied_rules=applied_rules,
            reasoning=" ".join(reasoning_parts),
            confidence=0.91,
        )

    @staticmethod
    def _build_searchable_text(voucher: VoucherExtraction) -> str:
        parts = [
            voucher.vendor_name,
            voucher.notes or "",
            " ".join(item.description for item in voucher.items),
        ]
        return " ".join(parts).lower()

    @staticmethod
    def _pick_credit_account(
        voucher: VoucherExtraction, skill: CompanySkill, accounts: dict
    ) -> str:
        if voucher.payment_method == PaymentMethod.BANK_TRANSFER and "1113" in accounts:
            return "1113"
        if voucher.payment_method == PaymentMethod.CASH and "1111" in accounts:
            return "1111"
        if voucher.total_amount >= Decimal("30000") and "1113" in accounts:
            return "1113"
        if skill.profile.default_payment_account in accounts:
            return skill.profile.default_payment_account
        for fallback in ("1112", "1111", "1113"):
            if fallback in accounts:
                return fallback
        return next(iter(accounts))

    @staticmethod
    def _parse_explicit_skill_override(
        text: str, skill_md: str, accounts: dict
    ) -> tuple[str, bool | None, str] | None:
        """支援使用者在 SKILL.md 寫「關鍵字 -> 科目代碼」來快速做 A/B 測試。"""
        pattern = re.compile(r"([^\s:：\-=>\*\`]+)\s*(?:->|=>|→)\s*`?(\d{4})`?")
        for raw_line in skill_md.splitlines():
            line = raw_line.strip()
            match = pattern.search(line)
            if not match:
                continue
            keyword, code = match.group(1).lower(), match.group(2)
            if keyword in text and code in accounts:
                deductible: bool | None = None
                if "不可扣抵" in line or "不得扣抵" in line:
                    deductible = False
                elif "可扣抵" in line:
                    deductible = True
                return code, deductible, line
        return None

    @staticmethod
    def _interpret_skill_markdown(
        voucher: VoucherExtraction,
        text: str,
        skill: CompanySkill,
        accounts: dict,
    ) -> tuple[str, bool, str] | None:
        """從 SKILL.md 段落語意中對應最符合的規則與科目。"""
        md = skill.skill_markdown

        # 1. 雲端 / SaaS
        if any(k in text for k in ("aws", "gcp", "azure", "雲端", "github", "openai", "notion")):
            if "6251" in accounts and "6251" in md:
                return "6251", True, "雲端與軟體訂閱歸 6251 雲端服務費"

        # 2. 咖啡 / 餐廳 / 星巴克（最經典的跨公司差異案例）
        if any(k in text for k in ("星巴克", "咖啡", "路易莎", "餐廳", "聚餐", "飲品", "那堤")):
            # 若 SKILL.md 明確把咖啡/星巴克歸入 5111 進貨成本（例如餐飲業）
            if "5111" in accounts and re.search(r"(咖啡|星巴克).*5111", md):
                return "5111", True, "咖啡與競品試飲歸 5111 進貨成本（可扣抵進項稅額）"
            # 否則檢視金額門檻與客戶關鍵字，區分交際費 vs 職工福利
            if any(k in text for k in ("客戶", "招待", "拜訪")) or voucher.total_amount > Decimal("2000"):
                if "6123" in accounts and "6123" in md:
                    return "6123", False, "招待客戶或逾 NT$2,000 餐飲歸 6123 交際費（不可扣抵）"
            if "6125" in accounts and "6125" in md:
                return "6125", False, "NT$2,000 以下內部會議茶水歸 6125 職工福利（不可扣抵）"

        # 3. 3C / 設備資本化判斷
        if any(k in text for k in ("macbook", "電腦", "螢幕", "筆電", "咖啡機", "設備", "主機")):
            threshold = skill.profile.capitalization_threshold
            if voucher.total_amount >= threshold:
                for asset_code in ("1641", "1651"):
                    if asset_code in accounts and asset_code in md:
                        return (
                            asset_code,
                            True,
                            f"金額 >= {threshold} 達資本化門檻，歸 {asset_code} {accounts[asset_code].name}",
                        )
            if "6116" in accounts and "6116" in md:
                return "6116", True, f"金額未達資本化門檻 ({threshold})，費用化歸 6116 雜項購置"

        # 4. 交通差旅
        if any(k in text for k in ("高鐵", "台鐵", "計程車", "加油", "uber")):
            if "6124" in accounts and "6124" in md:
                return "6124", True, "交通差旅歸 6124 旅費"

        # 5. 文具用品
        if any(k in text for k in ("文具", "影印紙", "碳粉", "原子筆", "書局")):
            if "6115" in accounts and "6115" in md:
                return "6115", True, "辦公文具歸 6115 文具用品"

        # 6. 水電與外送平台
        if any(k in text for k in ("台電", "電費", "水費", "瓦斯")) and "6122" in accounts:
            return "6122", True, "水電瓦斯費歸 6122 水電瓦斯費"
        if any(k in text for k in ("ubereats", "foodpanda", "平台抽成")) and "6241" in accounts:
            return "6241", True, "外送平台費用歸 6241 平台手續費"

        return None

    @staticmethod
    def _build_balanced_lines(
        voucher: VoucherExtraction,
        debit_code: str,
        credit_code: str,
        vat_deductible: bool,
        accounts: dict,
        vat_rate: Decimal,
    ) -> list[JournalLine]:
        total = voucher.total_amount
        lines: list[JournalLine] = []

        if vat_deductible:
            if voucher.subtotal is not None and voucher.tax_amount is not None:
                subtotal = voucher.subtotal
                tax = voucher.tax_amount
            else:
                # 若電子發票只印出含稅總計，以台灣營業稅 5% 內含回推未稅與稅額
                subtotal = (total / (Decimal("1") + vat_rate)).quantize(
                    Decimal("1"), rounding=ROUND_HALF_UP
                )
                tax = total - subtotal

            lines.append(
                JournalLine(
                    side=EntrySide.DEBIT,
                    account_code=debit_code,
                    account_name=accounts[debit_code].name,
                    amount=subtotal,
                    memo=f"{voucher.vendor_name} 未稅金額",
                )
            )
            if tax > Decimal("0"):
                lines.append(
                    JournalLine(
                        side=EntrySide.DEBIT,
                        account_code="1261",
                        account_name=accounts["1261"].name,
                        amount=tax,
                        memo="進項稅額 5%（可扣抵）",
                    )
                )
        else:
            lines.append(
                JournalLine(
                    side=EntrySide.DEBIT,
                    account_code=debit_code,
                    account_name=accounts[debit_code].name,
                    amount=total,
                    memo=f"{voucher.vendor_name}（含稅入帳／不可扣抵或無稅額）",
                )
            )

        lines.append(
            JournalLine(
                side=EntrySide.CREDIT,
                account_code=credit_code,
                account_name=accounts[credit_code].name,
                amount=total,
                memo=f"支付 {voucher.vendor_name}",
            )
        )
        return lines

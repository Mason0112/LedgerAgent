"""測試核心管線：驗證同一張憑證在不同公司 Skill 或修改 Skill 後產出不同分錄 JSON！"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ledger_agent.core.pipeline import LedgerPipeline
from ledger_agent.models.journal import EntrySide
from ledger_agent.models.voucher import VoucherExtraction, VoucherLineItem, VoucherType
from ledger_agent.providers.mock import MockLLMProvider
from ledger_agent.skills.loader import SkillLoader


def _sample_starbucks_voucher() -> VoucherExtraction:
    return VoucherExtraction(
        voucher_type=VoucherType.ELECTRONIC_INVOICE,
        voucher_number="AB-88234109",
        voucher_date="2026-11-24",
        vendor_name="悠旅生活事業股份有限公司(星巴克)",
        vendor_tax_id="16097091",
        subtotal=Decimal("1000"),
        tax_amount=Decimal("50"),
        total_amount=Decimal("1050"),
        items=[VoucherLineItem(description="特大杯美式咖啡 x5", amount=Decimal("1050"))],
    )


def test_same_voucher_different_company_skills_produce_different_entries(
    temp_companies_dir: Path,
) -> None:
    """核心驗證：同一張星巴克發票，科技業切 6125 職工福利(不可扣抵)，咖啡業切 5111 進貨成本(可扣抵)。"""
    loader = SkillLoader(temp_companies_dir)
    pipeline = LedgerPipeline(skill_loader=loader, provider=MockLLMProvider())
    voucher = _sample_starbucks_voucher()

    tech_out = pipeline.generate_for_voucher(voucher=voucher, company_id="demo_tech_co")
    cafe_out = pipeline.generate_for_voucher(voucher=voucher, company_id="demo_cafe_co")

    assert tech_out.is_valid is True
    assert cafe_out.is_valid is True

    tech_debits = [l for l in tech_out.generation.draft.lines if l.side == EntrySide.DEBIT]
    cafe_debits = [l for l in cafe_out.generation.draft.lines if l.side == EntrySide.DEBIT]

    # 科技公司：6125 職工福利 1050（含稅入帳，不拆進項稅額）
    assert tech_out.generation.draft.vat_deductible is False
    assert [l.account_code for l in tech_debits] == ["6125"]
    assert tech_debits[0].amount == Decimal("1050")

    # 咖啡公司：5111 進貨成本 1000 + 1261 進項稅額 50
    assert cafe_out.generation.draft.vat_deductible is True
    assert [l.account_code for l in cafe_debits] == ["5111", "1261"]
    assert cafe_debits[0].amount == Decimal("1000")
    assert cafe_debits[1].amount == Decimal("50")


def test_editing_skill_md_immediately_changes_output_json(
    temp_companies_dir: Path,
) -> None:
    """修改 SKILL.md 後重跑，立即改變產出的分錄科目與 skill_hash。"""
    loader = SkillLoader(temp_companies_dir)
    pipeline = LedgerPipeline(skill_loader=loader, provider=MockLLMProvider())
    voucher = _sample_starbucks_voucher()

    run1 = pipeline.generate_for_voucher(voucher=voucher, company_id="demo_tech_co")
    assert run1.generation.draft.lines[0].account_code == "6125"

    # 修改星辰科技的 SKILL.md：強制將星巴克全部歸入 6123 交際費
    current_skill = loader.load("demo_tech_co")
    loader.update_skill_markdown(
        "demo_tech_co",
        current_skill.skill_markdown + "\n- 測試新規則：星巴克 -> 6123 交際費（不可扣抵）\n",
    )

    run2 = pipeline.generate_for_voucher(voucher=voucher, company_id="demo_tech_co")
    assert run2.skill_hash != run1.skill_hash
    assert run2.generation.draft.lines[0].account_code == "6123"
    assert run2.generation.draft.vat_deductible is False

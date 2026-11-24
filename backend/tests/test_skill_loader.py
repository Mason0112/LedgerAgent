"""測試公司 Skill 載入、更新 SKILL.md、雜湊追蹤與歷史記憶檢索。"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from ledger_agent.models.skill import HistoryExample
from ledger_agent.models.voucher import VoucherExtraction, VoucherLineItem
from ledger_agent.skills.loader import SkillLoader
from ledger_agent.skills.memory import HistoryMemory


def test_list_and_load_companies(temp_companies_dir: Path) -> None:
    loader = SkillLoader(temp_companies_dir)
    companies = loader.list_companies()
    company_ids = [c.company_id for c in companies]

    assert "demo_tech_co" in company_ids
    assert "demo_cafe_co" in company_ids

    tech_skill = loader.load("demo_tech_co")
    assert tech_skill.profile.tax_id == "83124567"
    assert "6251" in tech_skill.account_map()
    assert len(tech_skill.vendor_rules) >= 2
    assert len(tech_skill.history_examples) >= 2


def test_update_skill_changes_hash(temp_companies_dir: Path) -> None:
    loader = SkillLoader(temp_companies_dir)
    before = loader.load("demo_tech_co")
    hash_before = loader.compute_skill_hash(before)

    updated = loader.update_skill_markdown(
        "demo_tech_co",
        before.skill_markdown + "\n- 星巴克 -> 6123 交際費（不可扣抵）\n",
    )
    hash_after = loader.compute_skill_hash(updated)

    assert hash_before != hash_after
    assert "星巴克 -> 6123" in updated.skill_markdown


def test_history_memory_retrieves_matching_vendor(temp_companies_dir: Path) -> None:
    loader = SkillLoader(temp_companies_dir)
    tech_skill = loader.load("demo_tech_co")

    voucher = VoucherExtraction(
        vendor_name="悠旅生活事業股份有限公司(星巴克)",
        vendor_tax_id="16097091",
        total_amount=Decimal("500"),
        items=[VoucherLineItem(description="美式咖啡 x2", amount=Decimal("500"))],
    )
    matched = HistoryMemory.retrieve(voucher, tech_skill.history_examples, top_k=2)
    assert len(matched) >= 1
    assert matched[0].example_id == "ex_tech_001"


def test_append_history_persists_to_jsonl(temp_companies_dir: Path) -> None:
    loader = SkillLoader(temp_companies_dir)
    before_count = len(loader.load("demo_cafe_co").history_examples)

    loader.append_history(
        "demo_cafe_co",
        HistoryExample(
            example_id="approved_test01",
            vendor_name="測試烘豆坊",
            vendor_tax_id="12345678",
            items_summary="耶加雪菲咖啡豆 5kg",
            total_amount="5250",
            entries=[],
            reasoning="測試寫入",
        ),
    )

    after = loader.load("demo_cafe_co")
    assert len(after.history_examples) == before_count + 1
    assert after.history_examples[-1].example_id == "approved_test01"

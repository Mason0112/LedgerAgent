"""FastAPI 端對端整合測試（上傳 -> 改 Skill -> 重跑對照 -> 核准寫入歷史）。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_and_companies_endpoints(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"

    res_co = client.get("/api/companies")
    assert res_co.status_code == 200
    ids = [c["company_id"] for c in res_co.json()]
    assert "demo_tech_co" in ids
    assert "demo_cafe_co" in ids


def test_full_skill_experiment_and_approval_flow(client: TestClient) -> None:
    # 1. 上傳一張測試發票至 demo_tech_co
    upload_res = client.post(
        "/api/vouchers/upload",
        data={"company_id": "demo_tech_co", "provider": "mock"},
        files={"file": ("starbucks_receipt.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    assert upload_res.status_code == 200
    detail = upload_res.json()
    voucher_id = detail["voucher_id"]
    assert len(detail["runs"]) == 1
    first_run = detail["runs"][0]
    assert first_run["journal_draft"]["lines"][0]["account_code"] == "6125"

    # 2. 即時修改 demo_tech_co 的 SKILL.md
    skill_res = client.get("/api/companies/demo_tech_co/skill")
    assert skill_res.status_code == 200
    old_md = skill_res.json()["skill"]["skill_markdown"]

    put_res = client.put(
        "/api/companies/demo_tech_co/skill",
        json={"skill_markdown": old_md + "\n- 星巴克 -> 6123 交際費（不可扣抵）\n"},
    )
    assert put_res.status_code == 200

    # 3. 針對同一張憑證重跑（不重做 OCR），驗證新 Run 科目已改為 6123
    rerun_res = client.post(
        f"/api/vouchers/{voucher_id}/rerun",
        json={"company_id": "demo_tech_co", "provider": "mock"},
    )
    assert rerun_res.status_code == 200
    detail_after = rerun_res.json()
    assert len(detail_after["runs"]) == 2
    latest_run = detail_after["runs"][0]
    assert latest_run["journal_draft"]["lines"][0]["account_code"] == "6123"
    assert latest_run["skill_hash"] != first_run["skill_hash"]

    # 4. 再用另一間公司 (demo_cafe_co) 試跑同一張憑證
    cafe_rerun = client.post(
        f"/api/vouchers/{voucher_id}/rerun",
        json={"company_id": "demo_cafe_co", "provider": "mock"},
    )
    assert cafe_rerun.status_code == 200
    cafe_detail = cafe_rerun.json()
    assert len(cafe_detail["runs"]) == 3
    assert cafe_detail["runs"][0]["journal_draft"]["lines"][0]["account_code"] == "5111"

    # 5. 核准最新一次 demo_tech_co 的 Run 並寫入 history.jsonl
    approve_res = client.post(
        f"/api/vouchers/{voucher_id}/runs/{latest_run['run_id']}/approve",
        json={"save_to_history": True},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"

    # 確認 history_examples 已新增一筆
    skill_after_approve = client.get("/api/companies/demo_tech_co/skill").json()
    ids = [ex["example_id"] for ex in skill_after_approve["skill"]["history_examples"]]
    assert f"approved_{latest_run['run_id'][:8]}" in ids

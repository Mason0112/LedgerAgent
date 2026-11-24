r"""使用 Python Playwright 自動操作 LedgerAgent 前後端並驗證 Skill 變更對 JSON 的影響。

執行前請確認：
1. PostgreSQL (Docker) 已啟動
2. 後端 FastAPI 運行於 http://localhost:8000
3. 前端 React Vite 運行於 http://localhost:5173

執行方式（預設會開啟可視瀏覽器視窗慢慢操作給你看）：
    .\.venv\Scripts\python.exe scripts\playwright_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
SLOW_MO = int(os.getenv("SLOW_MO", "650"))
SCREENSHOT_DIR = Path(
    os.getenv(
        "SCREENSHOT_DIR",
        str(Path(__file__).resolve().parents[2] / "playwright_screenshots"),
    )
)


def run_demo() -> None:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[Playwright] 目標網址: {FRONTEND_URL} (headless={HEADLESS}, slow_mo={SLOW_MO}ms)")
    print(f"[Playwright] 截圖儲存目錄: {SCREENSHOT_DIR}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS, slow_mo=SLOW_MO)
        context = browser.new_context(viewport={"width": 1440, "height": 960})
        page = context.new_page()

        # Step 1: 開啟 React 前端並確認連上 FastAPI + PostgreSQL，切換至星辰科技 (demo_tech_co)
        page.goto(FRONTEND_URL, wait_until="networkidle")
        expect(page.get_by_text("DB: connected")).to_be_visible(timeout=15000)
        page.locator("header select").first.select_option("demo_tech_co")
        expect(page.locator("textarea.skill-editor")).to_contain_text("星辰科技", timeout=10000)
        print("[Step 1] 成功連線前端與 PostgreSQL (DB: connected)，已選取 demo_tech_co")
        page.screenshot(path=str(SCREENSHOT_DIR / "01_initial_loaded.png"), full_page=True)

        # Step 2: 以「星辰科技 (demo_tech_co)」送出星巴克電子發票範例
        page.get_by_role("button", name="星巴克電子發票 ($1,050)").click()
        expect(page.locator("table.journal-table")).to_contain_text("6125", timeout=10000)
        expect(page.locator("table.journal-table")).to_contain_text("職工福利")
        print("[Step 2] 星辰科技 (demo_tech_co) 產出：借 6125 職工福利 1,050（不可扣抵）")
        page.screenshot(path=str(SCREENSHOT_DIR / "02_tech_co_6125.png"), full_page=True)

        # Step 3: 同一張憑證改用「晨光咖啡 (demo_cafe_co)」Skill 試跑
        page.get_by_role("button", name="用「晨光咖啡有限公司」Skill 試跑這張憑證").click()
        expect(page.locator("table.journal-table")).to_contain_text("5111", timeout=10000)
        expect(page.locator("table.journal-table")).to_contain_text("進貨成本")
        expect(page.locator("table.journal-table")).to_contain_text("1261")
        print("[Step 3] 晨光咖啡 (demo_cafe_co) 產出：借 5111 進貨成本 1,000 + 1261 進項稅額 50")
        page.screenshot(path=str(SCREENSHOT_DIR / "03_cafe_co_5111.png"), full_page=True)

        # Step 4: 即時修改 demo_tech_co 的 SKILL.md，把星巴克改歸 6123 交際費並重跑
        skill_editor = page.locator("textarea.skill-editor")
        original_skill_md = skill_editor.input_value()
        override_rule = "\n- 測試規則變更：星巴克 -> 6123 交際費（不可扣抵）\n"
        skill_editor.fill(original_skill_md + override_rule)

        page.get_by_role("button", name="儲存並用新 Skill 重跑目前憑證").click()
        expect(page.locator("table.journal-table")).to_contain_text("6123", timeout=10000)
        expect(page.locator("table.journal-table")).to_contain_text("交際費")
        print("[Step 4] 修改 SKILL.md 後重跑產出：借 6123 交際費 1,050（新 skill_hash 快照已保存）")

        # 捲動到 JSON 輸出區域並截圖展示最終結構化 JSON
        json_box = page.locator("pre.json-box").last
        json_box.scroll_into_view_if_needed()
        page.wait_for_timeout(800)
        page.screenshot(path=str(SCREENSHOT_DIR / "04_skill_edited_6123.png"), full_page=True)

        # Step 5: 還原 demo_tech_co 原始 SKILL.md，維持範例檔案整潔（但保留資料庫中的 3 筆 Run 對照紀錄）
        skill_editor.fill(original_skill_md)
        page.get_by_role("button", name="僅儲存 SKILL.md").click()
        expect(page.locator(".alert-ok")).to_be_visible(timeout=10000)
        print("[Step 5] 已還原 demo_tech_co 原始 SKILL.md，並保留 3 次 Run 快照於畫面與 PostgreSQL")

        if not HEADLESS:
            # 停頓 2 秒讓使用者看清楚最終結果再關閉 Playwright 視窗
            page.wait_for_timeout(2000)

        browser.close()
    print("[Playwright] 全部自動化操作與驗證完成！")


if __name__ == "__main__":
    try:
        run_demo()
    except Exception as exc:
        print(f"[Playwright] 執行失敗: {exc}", file=sys.stderr)
        raise

"""公司 Skill 檔案系統載入器。

負責讀取與更新 `companies/<company_id>/` 下的五個核心檔案：
1. company.yaml           - 公司基本資料與統編
2. SKILL.md               - 自然語言會計規則（核心客製化檔案）
3. chart_of_accounts.yaml - 專屬會計科目表
4. vendor_rules.yaml      - 廠商固定對應規則
5. history.jsonl          - 歷史核准分錄範例
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from ledger_agent.models.skill import (
    AccountItem,
    CompanyProfile,
    CompanySkill,
    HistoryExample,
    VendorRule,
)


class SkillNotFoundError(FileNotFoundError):
    """找不到指定公司的 Skill 資料夾時拋出。"""


class SkillLoader:
    """從檔案系統載入與管理各公司的客製化 Skills。"""

    def __init__(self, companies_dir: Path) -> None:
        self.companies_dir = companies_dir

    def list_companies(self) -> list[CompanyProfile]:
        """列出所有已設定的公司基本資料。"""
        if not self.companies_dir.exists():
            return []

        profiles: list[CompanyProfile] = []
        for entry in sorted(self.companies_dir.iterdir()):
            if entry.is_dir() and (entry / "company.yaml").exists():
                profiles.append(self._load_profile(entry))
        return profiles

    def load(self, company_id: str) -> CompanySkill:
        """載入指定公司的完整 Skill。"""
        company_dir = self._resolve_company_dir(company_id)

        profile = self._load_profile(company_dir)
        skill_md_path = company_dir / "SKILL.md"
        skill_markdown = (
            skill_md_path.read_text(encoding="utf-8") if skill_md_path.exists() else ""
        )

        accounts_raw = self._read_yaml(company_dir / "chart_of_accounts.yaml")
        accounts = [AccountItem(**item) for item in accounts_raw.get("accounts", [])]

        rules_raw = self._read_yaml(company_dir / "vendor_rules.yaml")
        vendor_rules = [VendorRule(**item) for item in rules_raw.get("rules", [])]

        history_examples = self._load_history(company_dir / "history.jsonl")

        return CompanySkill(
            profile=profile,
            skill_markdown=skill_markdown,
            chart_of_accounts=accounts,
            vendor_rules=vendor_rules,
            history_examples=history_examples,
        )

    def update_skill_markdown(self, company_id: str, new_markdown: str) -> CompanySkill:
        """覆寫指定公司的 SKILL.md，並回傳最新載入的 CompanySkill。"""
        company_dir = self._resolve_company_dir(company_id)
        (company_dir / "SKILL.md").write_text(new_markdown, encoding="utf-8")
        return self.load(company_id)

    def update_vendor_rules(
        self, company_id: str, rules: list[VendorRule]
    ) -> CompanySkill:
        """更新指定公司的 vendor_rules.yaml。"""
        company_dir = self._resolve_company_dir(company_id)
        payload = {"rules": [rule.model_dump() for rule in rules]}
        (company_dir / "vendor_rules.yaml").write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return self.load(company_id)

    def append_history(self, company_id: str, example: HistoryExample) -> None:
        """將人工核准後的分錄追加寫入該公司的 history.jsonl。"""
        company_dir = self._resolve_company_dir(company_id)
        history_path = company_dir / "history.jsonl"
        line = json.dumps(example.model_dump(), ensure_ascii=False)
        with history_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    @staticmethod
    def compute_skill_hash(skill: CompanySkill) -> str:
        """計算目前 Skill 內容的指紋雜湊，方便追蹤每次分錄對應的規則版本。"""
        canonical = json.dumps(
            {
                "skill_markdown": skill.skill_markdown,
                "accounts": [a.model_dump() for a in skill.chart_of_accounts],
                "vendor_rules": [r.model_dump() for r in skill.vendor_rules],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]

    def _resolve_company_dir(self, company_id: str) -> Path:
        # 防止路徑穿越攻擊（例如 ../）
        if "/" in company_id or "\\" in company_id or ".." in company_id:
            raise SkillNotFoundError(f"不合法的公司代碼: {company_id}")
        company_dir = self.companies_dir / company_id
        if not company_dir.is_dir() or not (company_dir / "company.yaml").exists():
            raise SkillNotFoundError(f"找不到公司 Skill: {company_id}")
        return company_dir

    def _load_profile(self, company_dir: Path) -> CompanyProfile:
        data = self._read_yaml(company_dir / "company.yaml")
        return CompanyProfile(**data)

    @staticmethod
    def _read_yaml(path: Path) -> dict:
        if not path.exists():
            return {}
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        return content if isinstance(content, dict) else {}

    @staticmethod
    def _load_history(path: Path) -> list[HistoryExample]:
        if not path.exists():
            return []
        examples: list[HistoryExample] = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            examples.append(HistoryExample(**json.loads(line)))
        return examples

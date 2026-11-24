"""Stage 2 & 3: 組合公司客製化 Skill 與 Prompt，呼叫 AI 生成結構化分錄草稿。"""

from __future__ import annotations

import json
from dataclasses import dataclass

from ledger_agent.models.journal import JournalEntryDraft
from ledger_agent.models.skill import CompanySkill, HistoryExample, VendorRule
from ledger_agent.models.voucher import VoucherExtraction
from ledger_agent.providers.base import BaseLLMProvider
from ledger_agent.skills.matcher import VendorRuleMatcher
from ledger_agent.skills.memory import HistoryMemory


@dataclass(slots=True)
class GenerationResult:
    """封裝分錄生成結果與所命中規則/記憶的追蹤資訊（便於可解釋性與除錯）。"""

    draft: JournalEntryDraft
    matched_rules: list[VendorRule]
    retrieved_examples: list[HistoryExample]
    system_prompt: str
    user_prompt: str


class JournalEntryGenerator:
    """根據公司 Skill、廠商規則與歷史範例組裝 Prompt 並產出分錄草稿。"""

    def __init__(self, provider: BaseLLMProvider) -> None:
        self.provider = provider

    def generate(
        self,
        voucher: VoucherExtraction,
        skill: CompanySkill,
        top_k_history: int = 3,
    ) -> GenerationResult:
        # Stage 2: 匹配確定性規則 + 檢索最相似的歷史分錄
        matched_rules = VendorRuleMatcher.match(voucher, skill.vendor_rules)
        retrieved_examples = HistoryMemory.retrieve(
            voucher, skill.history_examples, top_k=top_k_history
        )

        # 組裝系統提示詞與使用者提示詞
        system_prompt = self._build_system_prompt(skill)
        user_prompt = self._build_user_prompt(
            voucher=voucher,
            matched_rules=matched_rules,
            history_examples=retrieved_examples,
        )

        # Stage 3: 呼叫 LLM 生成嚴格符合 Schema 的 JSON 分錄
        draft = self.provider.generate_journal_entry(
            voucher=voucher,
            skill=skill,
            matched_rules=matched_rules,
            history_examples=retrieved_examples,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return GenerationResult(
            draft=draft,
            matched_rules=matched_rules,
            retrieved_examples=retrieved_examples,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    @staticmethod
    def _build_system_prompt(skill: CompanySkill) -> str:
        coa_lines = "\n".join(
            f"- {acc.code} | {acc.name} ({acc.category}, 正常餘額:{acc.normal_side}) — {acc.description}"
            for acc in skill.chart_of_accounts
        )
        return f"""你是一位專責服務「{skill.profile.name}」的資深台灣會計師 AI 助理。
你的任務是根據憑證 OCR 結構化 JSON，嚴格遵循本公司的專屬會計 Skill 與科目表，產出精確且借貸平衡的會計分錄 JSON。

【公司基本資料】
- 公司代碼：{skill.profile.company_id}
- 公司名稱：{skill.profile.name}
- 統一編號：{skill.profile.tax_id}
- 產業別：{skill.profile.industry}
- 預設幣別：{skill.profile.currency}
- 營業稅率：{skill.profile.vat_rate}
- 預設付款科目：{skill.profile.default_payment_account}
- 資本化門檻：{skill.profile.capitalization_threshold}

【本公司客製化 SKILL.md 規則（最高指導原則）】
{skill.skill_markdown}

【本公司合法會計科目表（嚴格白名單：只允許使用下列科目代碼）】
{coa_lines}

【硬性輸出規範】
1. 所有借方金額總和 MUST 嚴格等於所有貸方金額總和。
2. `account_code` 與 `account_name` 必須完全符合上述合法科目表，嚴禁自創科目代碼。
3. 請務必在 `applied_rules` 列出你套用的規則來源，並在 `reasoning` 清楚說明判斷邏輯。
"""

    @staticmethod
    def _build_user_prompt(
        voucher: VoucherExtraction,
        matched_rules: list[VendorRule],
        history_examples: list[HistoryExample],
    ) -> str:
        voucher_json = voucher.model_dump_json(indent=2)

        rules_block = (
            json.dumps(
                [r.model_dump() for r in matched_rules], ensure_ascii=False, indent=2
            )
            if matched_rules
            else "（無命中的廠商固定規則，請直接依 SKILL.md 與歷史範例判斷）"
        )

        history_block = (
            json.dumps(
                [ex.model_dump() for ex in history_examples], ensure_ascii=False, indent=2
            )
            if history_examples
            else "（無相似歷史範例）"
        )

        return f"""請針對以下憑證資料產出會計分錄 JSON：

### 1. 憑證解析結果 (VoucherExtraction)
```json
{voucher_json}
```

### 2. 命中的廠商固定規則 (vendor_rules.yaml)
```json
{rules_block}
```

### 3. 最相關的本公司歷史核准分錄 (Few-Shot Examples)
```json
{history_block}
```
"""

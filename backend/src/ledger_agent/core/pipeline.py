"""完整憑證切分錄管線（串接 Stage 1 ~ Stage 4）。

將「OCR 憑證辨識」與「依公司 Skill 生成分錄」拆分清楚，
因此修改 `SKILL.md` 後可以直接拿已解析的 JSON 重跑分錄，省去重複 OCR 的時間與費用！
"""

from __future__ import annotations

from dataclasses import dataclass

from ledger_agent.core.entry_generator import GenerationResult, JournalEntryGenerator
from ledger_agent.core.ocr_extractor import VoucherOCRExtractor
from ledger_agent.core.validator import AccountingValidator
from ledger_agent.models.journal import ValidationIssue
from ledger_agent.models.skill import CompanySkill
from ledger_agent.models.voucher import VoucherExtraction
from ledger_agent.providers.base import BaseLLMProvider
from ledger_agent.skills.loader import SkillLoader


@dataclass(slots=True)
class PipelineRunOutput:
    """管線單次執行的完整輸出結果。"""

    company_id: str
    provider_name: str
    model_name: str
    skill_hash: str
    voucher: VoucherExtraction
    generation: GenerationResult
    validation_issues: list[ValidationIssue]
    is_valid: bool
    recommended_status: str  # draft | needs_review


class LedgerPipeline:
    """協調 OCR、Company Skill 載入、AI 分錄生成與會計檢核。"""

    def __init__(self, skill_loader: SkillLoader, provider: BaseLLMProvider) -> None:
        self.skill_loader = skill_loader
        self.provider = provider
        self.extractor = VoucherOCRExtractor(provider)
        self.generator = JournalEntryGenerator(provider)

    def extract_only(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str | None = None,
    ) -> VoucherExtraction:
        """僅執行 Stage 1：憑證圖片/PDF -> 標準 VoucherExtraction JSON。"""
        return self.extractor.extract_from_bytes(
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type,
        )

    def generate_for_voucher(
        self,
        voucher: VoucherExtraction,
        company_id: str,
        existing_voucher_numbers: set[str] | None = None,
    ) -> PipelineRunOutput:
        """執行 Stage 2 ~ 4：載入最新公司 Skill -> 生成分錄 JSON -> 會計硬規則檢核。"""
        skill: CompanySkill = self.skill_loader.load(company_id)
        skill_hash = self.skill_loader.compute_skill_hash(skill)

        generation = self.generator.generate(voucher=voucher, skill=skill)
        issues = AccountingValidator.validate(
            voucher=voucher,
            draft=generation.draft,
            skill=skill,
            existing_voucher_numbers=existing_voucher_numbers,
        )
        has_errors = AccountingValidator.has_errors(issues)
        recommended_status = "needs_review" if issues else "draft"

        return PipelineRunOutput(
            company_id=company_id,
            provider_name=self.provider.provider_name,
            model_name=self.provider.model_name,
            skill_hash=skill_hash,
            voucher=voucher,
            generation=generation,
            validation_issues=issues,
            is_valid=not has_errors,
            recommended_status=recommended_status,
        )

    def process_file(
        self,
        file_bytes: bytes,
        filename: str,
        company_id: str,
        mime_type: str | None = None,
        existing_voucher_numbers: set[str] | None = None,
    ) -> PipelineRunOutput:
        """完整執行 Stage 1 ~ 4（上傳憑證檔案直接產出分錄）。"""
        voucher = self.extract_only(
            file_bytes=file_bytes,
            filename=filename,
            mime_type=mime_type,
        )
        return self.generate_for_voucher(
            voucher=voucher,
            company_id=company_id,
            existing_voucher_numbers=existing_voucher_numbers,
        )

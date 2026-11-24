"""資料存取層 (Repository Pattern)：封裝所有 PostgreSQL CRUD 查詢。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ledger_agent.core.pipeline import PipelineRunOutput
from ledger_agent.db.orm_models import JournalRunORM, VoucherORM
from ledger_agent.models.voucher import VoucherExtraction


class LedgerRepository:
    """封裝 Voucher 與 JournalRun 的資料庫讀寫操作。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_existing_voucher_numbers(
        self,
        company_id: str,
        exclude_voucher_id: str | None = None,
    ) -> set[str]:
        """查詢某公司已入庫的所有發票/憑證號碼，用於防範重複入帳。"""
        stmt = select(VoucherORM.voucher_number).where(
            VoucherORM.company_id == company_id,
            VoucherORM.voucher_number.is_not(None),
        )
        if exclude_voucher_id:
            stmt = stmt.where(VoucherORM.id != exclude_voucher_id)
        rows = self.db.execute(stmt).scalars().all()
        return {num.strip() for num in rows if num and num.strip()}

    def create_voucher_with_run(
        self,
        output: PipelineRunOutput,
        filename: str | None = None,
        file_path: str | None = None,
        mime_type: str | None = None,
    ) -> VoucherORM:
        """同時新增憑證紀錄與第一筆分錄執行快照。"""
        voucher_data = output.voucher.model_dump(mode="json")
        voucher_orm = VoucherORM(
            company_id=output.company_id,
            filename=filename,
            file_path=file_path,
            mime_type=mime_type,
            voucher_number=output.voucher.voucher_number,
            vendor_name=output.voucher.vendor_name,
            voucher_date=output.voucher.voucher_date,
            total_amount=str(output.voucher.total_amount),
            extraction_json=voucher_data,
        )
        self.db.add(voucher_orm)
        self.db.flush()  # 取得 voucher_orm.id

        run_orm = self._build_run_orm(voucher_id=voucher_orm.id, output=output)
        self.db.add(run_orm)
        self.db.commit()
        return self.get_voucher(voucher_orm.id)  # type: ignore[return-value]

    def add_run(self, voucher_id: str, output: PipelineRunOutput) -> JournalRunORM:
        """針對既有憑證新增一筆重跑後的分錄快照（用於測試修改 Skill 的影響）。"""
        run_orm = self._build_run_orm(voucher_id=voucher_id, output=output)
        self.db.add(run_orm)
        self.db.commit()
        self.db.expire_all()
        self.db.refresh(run_orm)
        return run_orm

    def list_vouchers(self, company_id: str | None = None) -> list[VoucherORM]:
        stmt = (
            select(VoucherORM)
            .options(selectinload(VoucherORM.runs))
            .order_by(VoucherORM.created_at.desc())
        )
        if company_id:
            stmt = stmt.where(VoucherORM.company_id == company_id)
        return list(self.db.execute(stmt).scalars().all())

    def get_voucher(self, voucher_id: str) -> VoucherORM | None:
        stmt = (
            select(VoucherORM)
            .options(selectinload(VoucherORM.runs))
            .where(VoucherORM.id == voucher_id)
            .execution_options(populate_existing=True)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_run(self, voucher_id: str, run_id: str) -> JournalRunORM | None:
        stmt = select(JournalRunORM).where(
            JournalRunORM.id == run_id,
            JournalRunORM.voucher_id == voucher_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def approve_run(
        self,
        run_orm: JournalRunORM,
        updated_draft_json: dict[str, Any] | None = None,
        validation_issues_json: list[dict[str, Any]] | None = None,
        is_valid: bool | None = None,
    ) -> JournalRunORM:
        """標記分錄為已核准，並可選擇保存人工微調後的 JSON。"""
        if updated_draft_json is not None:
            run_orm.journal_draft_json = updated_draft_json
        if validation_issues_json is not None:
            run_orm.validation_issues_json = validation_issues_json
        if is_valid is not None:
            run_orm.is_valid = is_valid
        run_orm.status = "approved"
        self.db.commit()
        self.db.refresh(run_orm)
        return run_orm

    @staticmethod
    def to_voucher_extraction(voucher_orm: VoucherORM) -> VoucherExtraction:
        return VoucherExtraction.model_validate(voucher_orm.extraction_json)

    @staticmethod
    def _build_run_orm(voucher_id: str, output: PipelineRunOutput) -> JournalRunORM:
        return JournalRunORM(
            voucher_id=voucher_id,
            company_id=output.company_id,
            provider=output.provider_name,
            model_name=output.model_name,
            status=output.recommended_status,
            skill_hash=output.skill_hash,
            matched_rule_ids=[r.rule_id for r in output.generation.matched_rules],
            retrieved_example_ids=[
                ex.example_id for ex in output.generation.retrieved_examples
            ],
            journal_draft_json=output.generation.draft.model_dump(mode="json"),
            validation_issues_json=[
                issue.model_dump(mode="json") for issue in output.validation_issues
            ],
            is_valid=output.is_valid,
            prompt_snapshot=output.generation.system_prompt,
        )

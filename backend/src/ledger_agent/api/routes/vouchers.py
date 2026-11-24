"""憑證上傳、JSON 測試、Skill 重跑對照與人工核准學習 API 路由。"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ledger_agent.config import Settings, get_settings
from ledger_agent.core.pipeline import LedgerPipeline
from ledger_agent.core.validator import AccountingValidator
from ledger_agent.db.database import get_db
from ledger_agent.db.orm_models import JournalRunORM, VoucherORM
from ledger_agent.db.repository import LedgerRepository
from ledger_agent.models.journal import (
    JournalEntryDraft,
    JournalRunResponse,
    ValidationIssue,
    VoucherDetailResponse,
    VoucherSummaryResponse,
)
from ledger_agent.models.skill import HistoryExample
from ledger_agent.models.voucher import VoucherExtraction
from ledger_agent.providers.factory import create_llm_provider
from ledger_agent.skills.loader import SkillLoader, SkillNotFoundError

router = APIRouter(prefix="/api/vouchers", tags=["vouchers"])


class CreateFromJsonRequest(BaseModel):
    """直接送入憑證 JSON 進行分錄測試（方便快速驗證不同公司 Skill 效果）。"""

    company_id: str
    extraction: VoucherExtraction
    provider: str | None = None
    filename: str | None = "manual_sample.json"


class RerunRequest(BaseModel):
    """修改 Skill 或切換公司/模型後，針對同一張憑證重跑分錄。"""

    company_id: str | None = None
    provider: str | None = None


class ApproveRunRequest(BaseModel):
    """核准分錄（可選擇帶入人工修改後的分錄草稿 JSON）並寫入公司歷史記憶。"""

    journal_draft: JournalEntryDraft | None = None
    save_to_history: bool = True


def _serialize_run(run: JournalRunORM) -> JournalRunResponse:
    return JournalRunResponse(
        run_id=run.id,
        voucher_id=run.voucher_id,
        company_id=run.company_id,
        provider=run.provider,
        model_name=run.model_name,
        status=run.status,
        skill_hash=run.skill_hash,
        matched_rule_ids=run.matched_rule_ids or [],
        retrieved_example_ids=run.retrieved_example_ids or [],
        journal_draft=run.journal_draft_json,
        validation_issues=[
            ValidationIssue.model_validate(item)
            for item in (run.validation_issues_json or [])
        ],
        is_valid=run.is_valid,
        created_at=run.created_at,
    )


def _serialize_voucher_detail(voucher: VoucherORM) -> VoucherDetailResponse:
    file_url = f"/uploads/{Path(voucher.file_path).name}" if voucher.file_path else None
    return VoucherDetailResponse(
        voucher_id=voucher.id,
        company_id=voucher.company_id,
        filename=voucher.filename,
        file_url=file_url,
        extraction=VoucherExtraction.model_validate(voucher.extraction_json),
        runs=[_serialize_run(run) for run in voucher.runs],
        created_at=voucher.created_at,
    )


@router.get("", response_model=list[VoucherSummaryResponse])
def list_vouchers(
    company_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[VoucherSummaryResponse]:
    """列出已處理的憑證清單（可依 company_id 篩選）。"""
    repo = LedgerRepository(db)
    vouchers = repo.list_vouchers(company_id=company_id)
    results: list[VoucherSummaryResponse] = []
    for v in vouchers:
        latest_status = v.runs[0].status if v.runs else "draft"
        results.append(
            VoucherSummaryResponse(
                voucher_id=v.id,
                company_id=v.company_id,
                filename=v.filename,
                vendor_name=v.vendor_name,
                voucher_number=v.voucher_number,
                voucher_date=v.voucher_date,
                total_amount=v.total_amount,
                latest_status=latest_status,
                runs_count=len(v.runs),
                created_at=v.created_at,
            )
        )
    return results


@router.post("/upload", response_model=VoucherDetailResponse)
async def upload_voucher(
    company_id: str = Form(...),
    provider: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> VoucherDetailResponse:
    """上傳憑證圖片或 PDF -> 執行 OCR 解析 -> 套用公司 Skill 產出分錄並寫入 PostgreSQL。"""
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="上傳的檔案內容為空")

    loader = SkillLoader(settings.companies_path)
    try:
        llm_provider = create_llm_provider(settings, provider_override=provider)
        pipeline = LedgerPipeline(skill_loader=loader, provider=llm_provider)

        repo = LedgerRepository(db)
        existing_numbers = repo.get_existing_voucher_numbers(company_id)

        output = pipeline.process_file(
            file_bytes=file_bytes,
            filename=file.filename or "voucher.jpg",
            company_id=company_id,
            mime_type=file.content_type,
            existing_voucher_numbers=existing_numbers,
        )
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 儲存原檔方便前端左欄預覽
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "voucher.jpg").suffix or ".bin"
    stored_name = f"{uuid4().hex}{ext}"
    stored_path = settings.upload_path / stored_name
    stored_path.write_bytes(file_bytes)

    voucher_orm = repo.create_voucher_with_run(
        output=output,
        filename=file.filename,
        file_path=str(stored_path),
        mime_type=file.content_type,
    )
    return _serialize_voucher_detail(voucher_orm)


@router.post("/from-json", response_model=VoucherDetailResponse)
def create_voucher_from_json(
    payload: CreateFromJsonRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> VoucherDetailResponse:
    """直接輸入憑證結構化 JSON（免上傳圖檔），立即測試公司 Skill 的分錄產出結果。"""
    loader = SkillLoader(settings.companies_path)
    try:
        llm_provider = create_llm_provider(settings, provider_override=payload.provider)
        pipeline = LedgerPipeline(skill_loader=loader, provider=llm_provider)

        repo = LedgerRepository(db)
        existing_numbers = repo.get_existing_voucher_numbers(payload.company_id)

        output = pipeline.generate_for_voucher(
            voucher=payload.extraction,
            company_id=payload.company_id,
            existing_voucher_numbers=existing_numbers,
        )
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    voucher_orm = repo.create_voucher_with_run(
        output=output,
        filename=payload.filename,
    )
    return _serialize_voucher_detail(voucher_orm)


@router.get("/{voucher_id}", response_model=VoucherDetailResponse)
def get_voucher(
    voucher_id: str,
    db: Session = Depends(get_db),
) -> VoucherDetailResponse:
    """取得單一憑證的完整 OCR JSON 與歷次分錄 Run 快照。"""
    repo = LedgerRepository(db)
    voucher = repo.get_voucher(voucher_id)
    if voucher is None:
        raise HTTPException(status_code=404, detail=f"找不到憑證: {voucher_id}")
    return _serialize_voucher_detail(voucher)


@router.post("/{voucher_id}/rerun", response_model=VoucherDetailResponse)
def rerun_voucher(
    voucher_id: str,
    payload: RerunRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> VoucherDetailResponse:
    """核心實驗功能：不重跑 OCR，直接用最新 SKILL.md（或切換另一間公司/模型）重跑分錄並保存新快照！"""
    repo = LedgerRepository(db)
    voucher = repo.get_voucher(voucher_id)
    if voucher is None:
        raise HTTPException(status_code=404, detail=f"找不到憑證: {voucher_id}")

    target_company_id = payload.company_id or voucher.company_id
    loader = SkillLoader(settings.companies_path)
    try:
        llm_provider = create_llm_provider(settings, provider_override=payload.provider)
        pipeline = LedgerPipeline(skill_loader=loader, provider=llm_provider)
        extraction = repo.to_voucher_extraction(voucher)
        existing_numbers = repo.get_existing_voucher_numbers(
            target_company_id, exclude_voucher_id=voucher.id
        )
        output = pipeline.generate_for_voucher(
            voucher=extraction,
            company_id=target_company_id,
            existing_voucher_numbers=existing_numbers,
        )
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    repo.add_run(voucher_id=voucher.id, output=output)
    refreshed = repo.get_voucher(voucher.id)
    assert refreshed is not None
    return _serialize_voucher_detail(refreshed)


@router.post("/{voucher_id}/runs/{run_id}/approve", response_model=JournalRunResponse)
def approve_run(
    voucher_id: str,
    run_id: str,
    payload: ApproveRunRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JournalRunResponse:
    """核准特定分錄快照，並自動將結果追加至該公司的 history.jsonl 形成學習閉環。"""
    repo = LedgerRepository(db)
    voucher = repo.get_voucher(voucher_id)
    if voucher is None:
        raise HTTPException(status_code=404, detail=f"找不到憑證: {voucher_id}")

    run = repo.get_run(voucher_id=voucher_id, run_id=run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"找不到分錄執行紀錄: {run_id}")

    loader = SkillLoader(settings.companies_path)
    skill = loader.load(run.company_id)
    extraction = repo.to_voucher_extraction(voucher)

    final_draft = (
        payload.journal_draft
        if payload.journal_draft is not None
        else JournalEntryDraft.model_validate(run.journal_draft_json)
    )
    issues = AccountingValidator.validate(
        voucher=extraction,
        draft=final_draft,
        skill=skill,
        existing_voucher_numbers=repo.get_existing_voucher_numbers(
            run.company_id, exclude_voucher_id=voucher.id
        ),
    )
    if AccountingValidator.has_errors(issues):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "分錄仍有會計檢核 ERROR（例如借貸不平或非法科目），請修正後再核准。",
                "issues": [i.model_dump(mode="json") for i in issues],
            },
        )

    approved = repo.approve_run(
        run_orm=run,
        updated_draft_json=final_draft.model_dump(mode="json"),
        validation_issues_json=[i.model_dump(mode="json") for i in issues],
        is_valid=True,
    )

    if payload.save_to_history:
        items_summary = (
            "、".join(item.description for item in extraction.items)
            or extraction.vendor_name
        )
        example = HistoryExample(
            example_id=f"approved_{run.id[:8]}",
            vendor_name=extraction.vendor_name,
            vendor_tax_id=extraction.vendor_tax_id,
            voucher_type=extraction.voucher_type.value,
            items_summary=items_summary,
            total_amount=str(extraction.total_amount),
            entries=[line.model_dump(mode="json") for line in final_draft.lines],
            reasoning=final_draft.reasoning,
        )
        loader.append_history(run.company_id, example)

    return _serialize_run(approved)

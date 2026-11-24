"""公司管理與客製化 Skill 編輯 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ledger_agent.config import Settings, get_settings
from ledger_agent.models.skill import CompanyProfile, CompanySkill, VendorRule
from ledger_agent.skills.loader import SkillLoader, SkillNotFoundError

router = APIRouter(prefix="/api/companies", tags=["companies"])


class SkillDetailResponse(BaseModel):
    skill_hash: str
    skill: CompanySkill


class UpdateSkillMarkdownRequest(BaseModel):
    skill_markdown: str


class UpdateVendorRulesRequest(BaseModel):
    rules: list[VendorRule]


def _get_loader(settings: Settings = Depends(get_settings)) -> SkillLoader:
    return SkillLoader(settings.companies_path)


@router.get("", response_model=list[CompanyProfile])
def list_companies(loader: SkillLoader = Depends(_get_loader)) -> list[CompanyProfile]:
    """取得所有已設定客製化 Skill 的公司清單。"""
    return loader.list_companies()


@router.get("/{company_id}/skill", response_model=SkillDetailResponse)
def get_company_skill(
    company_id: str,
    loader: SkillLoader = Depends(_get_loader),
) -> SkillDetailResponse:
    """取得指定公司的完整 Skill（含 SKILL.md、科目表、廠商規則與歷史記憶）。"""
    try:
        skill = loader.load(company_id)
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SkillDetailResponse(
        skill_hash=loader.compute_skill_hash(skill),
        skill=skill,
    )


@router.put("/{company_id}/skill", response_model=SkillDetailResponse)
def update_company_skill(
    company_id: str,
    payload: UpdateSkillMarkdownRequest,
    loader: SkillLoader = Depends(_get_loader),
) -> SkillDetailResponse:
    """即時更新指定公司的 SKILL.md 內容（修改後即可對憑證一鍵重跑對照 JSON 差異）。"""
    try:
        updated = loader.update_skill_markdown(company_id, payload.skill_markdown)
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SkillDetailResponse(
        skill_hash=loader.compute_skill_hash(updated),
        skill=updated,
    )


@router.put("/{company_id}/vendor-rules", response_model=SkillDetailResponse)
def update_company_vendor_rules(
    company_id: str,
    payload: UpdateVendorRulesRequest,
    loader: SkillLoader = Depends(_get_loader),
) -> SkillDetailResponse:
    """更新指定公司的 vendor_rules.yaml。"""
    try:
        updated = loader.update_vendor_rules(company_id, payload.rules)
    except SkillNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SkillDetailResponse(
        skill_hash=loader.compute_skill_hash(updated),
        skill=updated,
    )

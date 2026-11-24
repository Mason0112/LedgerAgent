"""SQLAlchemy 2.0 ORM 資料表定義。

核心設計（兩張表，一對多關係）：
- `vouchers`: 存放每張憑證的原檔資訊與 OCR 解析後的 `extraction_json`。
- `journal_runs`: 存放每次套用特定公司 Skill 所產出的分錄快照 JSON。
  -> 修改 SKILL.md 後重跑會新增一筆 `journal_runs`，讓你清楚比較改 Skill 前後的 JSON 差異！
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ledger_agent.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VoucherORM(Base):
    """已上傳或匯入的憑證主表。"""

    __tablename__ = "vouchers"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    company_id: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    voucher_number: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    vendor_name: Mapped[str] = mapped_column(String(255))
    voucher_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    total_amount: Mapped[str] = mapped_column(String(32))
    extraction_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    # 一張憑證可對應多次不同 Skill 版本或不同公司的分錄執行結果
    runs: Mapped[list[JournalRunORM]] = relationship(
        back_populates="voucher",
        cascade="all, delete-orphan",
        order_by="desc(JournalRunORM.created_at)",
    )


class JournalRunORM(Base):
    """單次套用公司 Skill 產出的分錄快照表。"""

    __tablename__ = "journal_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    voucher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("vouchers.id", ondelete="CASCADE"), index=True
    )
    company_id: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    model_name: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="draft")  # draft | needs_review | approved
    skill_hash: Mapped[str] = mapped_column(String(32))
    matched_rule_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    retrieved_example_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    journal_draft_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    validation_issues_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)
    prompt_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    voucher: Mapped[VoucherORM] = relationship(back_populates="runs")

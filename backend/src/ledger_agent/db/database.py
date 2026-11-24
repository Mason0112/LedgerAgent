"""SQLAlchemy 2.0 資料庫連線與 Session 管理。

Python 學習重點：
- `Generator[Session, None, None]` 搭配 `yield` 是 FastAPI 依賴注入（Dependency Injection）的標準寫法，
  可確保每個 HTTP 請求結束後自動關閉資料庫連線。
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ledger_agent.config import get_settings


class Base(DeclarativeBase):
    """所有 ORM 資料表模型的共同基底類別。"""


def create_db_engine(database_url: str | None = None) -> Engine:
    url = database_url or get_settings().database_url
    connect_args: dict = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


# 預設的全域 Engine 與 SessionLocal（測試環境可透過 FastAPI dependency_overrides 替換）
_engine = create_db_engine()
SessionLocal = create_session_factory(_engine)


def init_db(engine: Engine | None = None) -> None:
    """建立尚未存在的資料表（MVP 階段自動建表，後續可引入 Alembic 做 migration）。"""
    # 確保 ORM 模型已匯入以註冊至 Base.metadata
    from ledger_agent.db import orm_models  # noqa: F401

    target_engine = engine or _engine
    Base.metadata.create_all(bind=target_engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依賴注入：為每個 Request 提供獨立的資料庫 Session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

"""pytest 共用測試夾具 (Fixtures)。

Python 學習重點：
- 測試中使用暫存目錄複製 `companies/`，避免測試寫入 `history.jsonl` 或修改 `SKILL.md` 汙染正式設定。
- 使用 FastAPI 的 `app.dependency_overrides` 替換資料庫 Session 與 Settings，讓測試完全隔離且飛快！
"""

from __future__ import annotations

import shutil
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from ledger_agent.api.app import create_app
from ledger_agent.config import Settings, get_settings
from ledger_agent.db.database import (
    Base,
    create_db_engine,
    create_session_factory,
    get_db,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_COMPANIES_DIR = REPO_ROOT / "companies"


@pytest.fixture
def temp_companies_dir(tmp_path: Path) -> Path:
    """複製範例公司 Skills 至測試暫存資料夾，避免改動汙染專案檔案。"""
    target = tmp_path / "companies"
    shutil.copytree(SOURCE_COMPANIES_DIR, target)
    return target


@pytest.fixture
def client(tmp_path: Path, temp_companies_dir: Path) -> Generator[TestClient, None, None]:
    """建立使用獨立測試資料庫與獨立暫存公司目錄的 FastAPI TestClient。"""
    db_file = tmp_path / "test_ledger.db"
    engine = create_db_engine(f"sqlite:///{db_file}")
    from ledger_agent.db import orm_models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = create_session_factory(engine)

    test_settings = Settings(
        database_url=f"sqlite:///{db_file}",
        llm_provider="mock",
        companies_dir=str(temp_companies_dir),
        upload_dir=str(tmp_path / "uploads"),
    )

    app = create_app(initialize_db=False, settings_override=test_settings)

    def _override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_settings] = lambda: test_settings

    with TestClient(app) as test_client:
        yield test_client

    engine.dispose()

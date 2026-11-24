"""FastAPI 主應用程式進入點。

啟動方式（在 backend/ 目錄下）：
    uvicorn ledger_agent.api.app:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from ledger_agent.api.routes import companies, vouchers
from ledger_agent.config import Settings, get_settings
from ledger_agent.db.database import get_db, init_db


def create_app(
    initialize_db: bool = True,
    settings_override: Settings | None = None,
) -> FastAPI:
    """應用程式工廠函式（方便在單元測試中建立獨立 App 實例，且匯入模組無副作用）。"""
    settings = settings_override or get_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        settings.upload_path.mkdir(parents=True, exist_ok=True)
        if initialize_db:
            init_db()
        yield

    app = FastAPI(
        title="LedgerAgent API",
        description="多模態憑證 OCR + 每間公司客製化 AI Skills 自動切分錄引擎",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 前後端分離必備：設定 CORS 允許 React 前端跨域存取
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 提供已上傳憑證圖片預覽的靜態檔案路徑 (check_dir=False 避免匯入時強制建立目錄)
    app.mount(
        "/uploads",
        StaticFiles(directory=str(settings.upload_path), check_dir=False),
        name="uploads",
    )

    # 註冊 API 路由
    app.include_router(companies.router)
    app.include_router(vouchers.router)

    @app.get("/api/health", tags=["system"])
    def health_check(
        db: Session = Depends(get_db),
        cfg: Settings = Depends(get_settings),
    ) -> dict:
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "database": "connected",
            "default_provider": cfg.llm_provider,
            "available_providers": {
                "mock": True,
                "gemini": bool(cfg.gemini_api_key),
                "openai": bool(cfg.openai_api_key or cfg.openai_base_url),
            },
        }

    return app


app = create_app()

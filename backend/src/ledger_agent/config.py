"""應用程式環境設定模組（使用 pydantic-settings 自動讀取 .env 檔案）。

Python 學習重點：
- `BaseSettings` 會自動從環境變數與 `.env` 載入設定並做型別驗證。
- `Path`（來自 `pathlib`）是現代 Python 處理跨平台檔案路徑的標準寫法。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


# 以此檔案位置回推 backend/ 根目錄，避免執行目錄不同造成相對路徑失效
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """集中管理資料庫、AI 模型供應商與檔案路徑設定。"""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL 資料庫連線字串 (SQLAlchemy 2.0 + psycopg3)
    database_url: str = (
        "postgresql+psycopg://ledger:ledger_dev_password@localhost:5432/ledger_agent"
    )

    # AI 模型供應商選擇：mock | gemini | openai
    llm_provider: str = "mock"

    # Google Gemini 設定
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # OpenAI / OpenAI-Compatible (如 Ollama) 設定
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""

    # 公司 Skills 資料夾與上傳憑證儲存目錄
    companies_dir: str = "../companies"
    upload_dir: str = "./uploads"

    # 前端 CORS 允許來源（逗號分隔）
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def companies_path(self) -> Path:
        path = Path(self.companies_dir)
        return path if path.is_absolute() else (BACKEND_ROOT / path).resolve()

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        return path if path.is_absolute() else (BACKEND_ROOT / path).resolve()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """快取 Settings 實例（單例模式），避免重複讀取 .env。"""
    return Settings()

# LedgerAgent — AI 憑證解析 + 公司客製化 Skills 自動切分錄系統

透過多模態 VLM（Gemini / OpenAI / 離線 Mock）解析台灣基礎憑證，動態載入每間公司專屬的 `SKILL.md`、`chart_of_accounts.yaml`、`vendor_rules.yaml` 與 `history.jsonl`，自動產出結構化借貸分錄 JSON，並經由程式化會計硬規則檢核與人工審核閉環學習。

---

## 專案架構（前後端分離 + Docker PostgreSQL）

```text
LedgerAgent/
├── docker-compose.yml       # PostgreSQL 16 資料庫
├── companies/               # 每間公司獨立的客製化 Skills
│   ├── demo_tech_co/        # 範例公司 A：星辰科技（軟體業）
│   └── demo_cafe_co/        # 範例公司 B：晨光咖啡（餐飲業）
├── backend/                 # Python FastAPI 後端
│   ├── src/ledger_agent/
│   │   ├── config.py        # pydantic-settings 環境設定
│   │   ├── models/          # Pydantic v2 JSON Schema（Decimal 精準金額）
│   │   ├── skills/          # SkillLoader / VendorRuleMatcher / HistoryMemory
│   │   ├── providers/       # 可抽換多模態 AI 層 (mock / gemini / openai)
│   │   ├── core/            # OCR -> Skill Prompt -> Validator -> Pipeline
│   │   ├── db/              # SQLAlchemy 2.0 + PostgreSQL ORM 與 Repository
│   │   └── api/             # FastAPI REST 路由（含 Swagger /docs）
│   └── tests/               # pytest 單元與整合測試
└── frontend/                # React + TypeScript + Vite 輕量審核與 Skill 實驗室
    └── src/
        ├── types.ts         # 對應後端 Pydantic Schema 的 TypeScript 嚴格型別定義
        ├── api.ts           # 型別安全 API Client
        └── App.tsx          # 憑證上傳、SKILL.md 編輯與分錄 JSON 對照介面
```

---

## 快速啟動步驟

### 1. 啟動 PostgreSQL 資料庫（Docker）
```powershell
docker compose up -d
```

### 2. 啟動 Python 後端 (FastAPI)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn ledger_agent.api.app:app --reload --port 8000
```
- API 互動文件（Swagger UI）：`http://localhost:8000/docs`
- 預設 `LLM_PROVIDER=mock`（免 API Key 即可完整體驗）；若要接真實多模態 AI，編輯 `backend/.env`：
  ```dotenv
  LLM_PROVIDER=gemini
  GEMINI_API_KEY=你的_GEMINI_API_KEY
  ```

### 3. 啟動 React 前端
```powershell
cd frontend
npm install
npm run dev
```
打開瀏覽器前往 `http://localhost:5173`。

### 4. 執行自動化測試
```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -v
```

---

## 建議實驗流程（驗證 Skill 改變如何影響 JSON 產出）

1. 在前端點選 **「星巴克電子發票 ($1,050)」**（使用 `demo_tech_co`）：
   - 觀察 JSON 輸出：借 `6125 職工福利 1,050`（進項不可扣抵）、貸 `1112 零用金 1,050`。
2. 在右側直接點擊 **「用『晨光咖啡有限公司』Skill 試跑這張憑證」**：
   - 同一張憑證不重做 OCR，新快照改切：借 `5111 進貨成本 1,000` + `1261 進項稅額 50`、貸 `1111 現金 1,050`。
3. 在左側修改 `demo_tech_co` 的 `SKILL.md`（例如加上 `星巴克 -> 6123 交際費（不可扣抵）`）後按 **「儲存並用新 Skill 重跑目前憑證」**：
   - 上方會新增一個 Run 頁籤與新的 `skill_hash`，可來回點選比較兩次分錄 JSON 差異！

---

## Python 學習導讀路線

如果你想順便學習現代 Python 後端開發，建議依照以下順序閱讀 `backend/src/ledger_agent/`：
1. `models/voucher.py` & `models/journal.py` — 學習 `Enum`、`Decimal` 與 **Pydantic v2** 強型別資料驗證。
2. `config.py` — 學習 `pathlib.Path` 與 `pydantic-settings` 管理 `.env`。
3. `skills/loader.py` & `skills/memory.py` — 學習檔案讀寫、YAML/JSONL 解析與純 Python 演算法。
4. `providers/base.py` & `providers/factory.py` — 學習 **抽象類別 (`ABC`)** 與 **策略/工廠設計模式**。
5. `core/validator.py` & `core/pipeline.py` — 學習 `dataclass` 與將業務邏輯從 API 框架解耦。
6. `db/orm_models.py` & `db/repository.py` — 學習 **SQLAlchemy 2.0** 型別化 ORM 與 Repository 模式。
7. `api/routes/vouchers.py` — 學習 **FastAPI** 路由、`Depends` 依賴注入與 `pytest` + `TestClient` 測試。

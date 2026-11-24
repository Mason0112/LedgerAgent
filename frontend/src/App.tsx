import { useEffect, useState, type ChangeEvent } from "react";
import { api } from "./api";
import type {
  CompanyProfile,
  HealthResponse,
  JournalRunResponse,
  ProviderName,
  SampleVoucherPreset,
  SkillDetailResponse,
  VoucherDetailResponse,
  VoucherSummaryResponse,
} from "./types";

// 內建 3 張台灣常見範例憑證，方便一鍵測試不同公司 Skill 的 JSON 產出差異
const SAMPLE_VOUCHERS: SampleVoucherPreset[] = [
  {
    label: "星巴克電子發票 ($1,050)",
    filename: "sample_starbucks.json",
    extraction: {
      voucher_type: "electronic_invoice",
      voucher_number: "AB-88234109",
      voucher_date: "2026-11-24",
      vendor_name: "悠旅生活事業股份有限公司(星巴克)",
      vendor_tax_id: "16097091",
      buyer_tax_id: "83124567",
      currency: "TWD",
      subtotal: "1000",
      tax_amount: "50",
      total_amount: "1050",
      payment_method: "petty_cash",
      items: [
        { description: "特大杯美式咖啡 x3", quantity: "3", unit_price: "140", amount: "420" },
        { description: "那堤咖啡 x4", quantity: "4", unit_price: "157.5", amount: "630" },
      ],
      notes: "內部會議飲品 / 競品試飲",
      confidence: 0.95,
    },
  },
  {
    label: "AWS 雲端月費三聯發票 ($10,500)",
    filename: "sample_aws_cloud.json",
    extraction: {
      voucher_type: "triplicate_invoice",
      voucher_number: "CD-44882910",
      voucher_date: "2026-11-24",
      vendor_name: "台灣亞馬遜雲端服務有限公司 (AWS)",
      vendor_tax_id: "54321987",
      buyer_tax_id: "83124567",
      currency: "TWD",
      subtotal: "10000",
      tax_amount: "500",
      total_amount: "10500",
      payment_method: "bank_transfer",
      items: [
        {
          description: "AWS EC2 & RDS 雲端伺服器月費",
          quantity: "1",
          unit_price: "10000",
          amount: "10000",
        },
      ],
      notes: "正式環境主機月費",
      confidence: 0.97,
    },
  },
  {
    label: "MacBook Pro 設備發票 ($89,250)",
    filename: "sample_macbook.json",
    extraction: {
      voucher_type: "triplicate_invoice",
      voucher_number: "EF-77120394",
      voucher_date: "2026-11-24",
      vendor_name: "蘋果商務經銷有限公司",
      vendor_tax_id: "28991122",
      buyer_tax_id: "83124567",
      currency: "TWD",
      subtotal: "85000",
      tax_amount: "4250",
      total_amount: "89250",
      payment_method: "bank_transfer",
      items: [
        {
          description: "MacBook Pro 16吋 研發工作站",
          quantity: "1",
          unit_price: "85000",
          amount: "85000",
        },
      ],
      notes: "新進工程師筆電設備採購",
      confidence: 0.96,
    },
  },
];

function getErrorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [companies, setCompanies] = useState<CompanyProfile[]>([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState<string>("");
  const [provider, setProvider] = useState<ProviderName>("mock");

  const [skillDetail, setSkillDetail] = useState<SkillDetailResponse | null>(null);
  const [skillDraftMd, setSkillDraftMd] = useState<string>("");
  const [skillDirty, setSkillDirty] = useState<boolean>(false);

  const [vouchers, setVouchers] = useState<VoucherSummaryResponse[]>([]);
  const [activeVoucher, setActiveVoucher] = useState<VoucherDetailResponse | null>(null);
  const [selectedRunIndex, setSelectedRunIndex] = useState<number>(0);

  const [busy, setBusy] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const [toastMsg, setToastMsg] = useState<string>("");

  const showToast = (msg: string) => {
    setToastMsg(msg);
    window.setTimeout(() => setToastMsg(""), 3500);
  };

  // 初始化載入系統狀態、公司列表與憑證清單
  useEffect(() => {
    void (async () => {
      try {
        const [h, coList, vList] = await Promise.all([
          api.health(),
          api.listCompanies(),
          api.listVouchers(),
        ]);
        setHealth(h);
        setProvider(h.default_provider || "mock");
        setCompanies(coList);
        setVouchers(vList);
        if (coList.length > 0) {
          setSelectedCompanyId(coList[0].company_id);
        }
        if (vList.length > 0) {
          const firstDetail = await api.getVoucher(vList[0].voucher_id);
          setActiveVoucher(firstDetail);
        }
      } catch (err) {
        setErrorMsg(`無法連線至後端 API：${getErrorMessage(err)}`);
      }
    })();
  }, []);

  // 切換公司時載入對應的 SKILL.md、科目表與歷史記憶
  useEffect(() => {
    if (!selectedCompanyId) return;
    void (async () => {
      try {
        const data = await api.getCompanySkill(selectedCompanyId);
        setSkillDetail(data);
        setSkillDraftMd(data.skill.skill_markdown);
        setSkillDirty(false);
      } catch (err) {
        setErrorMsg(getErrorMessage(err));
      }
    })();
  }, [selectedCompanyId]);

  const refreshVoucherList = async (): Promise<void> => {
    const list = await api.listVouchers();
    setVouchers(list);
  };

  const handleSelectVoucher = async (voucherId: string): Promise<void> => {
    setErrorMsg("");
    setBusy(true);
    try {
      const detail = await api.getVoucher(voucherId);
      setActiveVoucher(detail);
      setSelectedRunIndex(0);
    } catch (err) {
      setErrorMsg(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>): Promise<void> => {
    const file = e.target.files?.[0];
    if (!file || !selectedCompanyId) return;
    setErrorMsg("");
    setBusy(true);
    try {
      const detail = await api.uploadVoucher(selectedCompanyId, file, provider);
      setActiveVoucher(detail);
      setSelectedRunIndex(0);
      await refreshVoucherList();
      showToast(`已解析 ${file.name} 並產出分錄 JSON！`);
    } catch (err) {
      setErrorMsg(getErrorMessage(err));
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  };

  const handleSampleVoucher = async (sample: SampleVoucherPreset): Promise<void> => {
    if (!selectedCompanyId) return;
    setErrorMsg("");
    setBusy(true);
    try {
      const detail = await api.createFromJson(
        selectedCompanyId,
        sample.extraction,
        provider,
        sample.filename
      );
      setActiveVoucher(detail);
      setSelectedRunIndex(0);
      await refreshVoucherList();
      showToast(`已使用 ${selectedCompanyId} 測試「${sample.label}」`);
    } catch (err) {
      setErrorMsg(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleSaveSkill = async (andRerun = false): Promise<void> => {
    if (!selectedCompanyId) return;
    setErrorMsg("");
    setBusy(true);
    try {
      const updated = await api.updateCompanySkill(selectedCompanyId, skillDraftMd);
      setSkillDetail(updated);
      setSkillDirty(false);
      if (andRerun && activeVoucher) {
        const rerunDetail = await api.rerunVoucher(
          activeVoucher.voucher_id,
          selectedCompanyId,
          provider
        );
        setActiveVoucher(rerunDetail);
        setSelectedRunIndex(0);
        await refreshVoucherList();
        showToast(`已更新 ${selectedCompanyId} 的 SKILL.md 並產生新的分錄快照！`);
      } else {
        showToast(`已儲存 ${selectedCompanyId} 的 SKILL.md (hash: ${updated.skill_hash})`);
      }
    } catch (err) {
      setErrorMsg(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleRerunWithCompany = async (targetCompanyId: string): Promise<void> => {
    if (!activeVoucher) return;
    setErrorMsg("");
    setBusy(true);
    try {
      const detail = await api.rerunVoucher(
        activeVoucher.voucher_id,
        targetCompanyId,
        provider
      );
      setActiveVoucher(detail);
      setSelectedRunIndex(0);
      await refreshVoucherList();
      showToast(`已用 ${targetCompanyId} 重跑分錄，可點擊上方 Run 頁籤對照差異！`);
    } catch (err) {
      setErrorMsg(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleApproveRun = async (run: JournalRunResponse): Promise<void> => {
    if (!activeVoucher) return;
    setErrorMsg("");
    setBusy(true);
    try {
      await api.approveRun(activeVoucher.voucher_id, run.run_id, true);
      const refreshed = await api.getVoucher(activeVoucher.voucher_id);
      setActiveVoucher(refreshed);
      await refreshVoucherList();
      if (run.company_id === selectedCompanyId) {
        const updatedSkill = await api.getCompanySkill(selectedCompanyId);
        setSkillDetail(updatedSkill);
      }
      showToast(`已核准分錄並寫入 ${run.company_id}/history.jsonl 學習庫！`);
    } catch (err) {
      setErrorMsg(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const activeRun: JournalRunResponse | null =
    activeVoucher?.runs?.[selectedRunIndex] ?? null;
  const draftLines = activeRun?.journal_draft.lines ?? [];
  const totalDebit = draftLines
    .filter((l) => l.side === "debit")
    .reduce((acc, l) => acc + Number(l.amount || 0), 0);
  const totalCredit = draftLines
    .filter((l) => l.side === "credit")
    .reduce((acc, l) => acc + Number(l.amount || 0), 0);

  return (
    <div>
      <header className="topbar">
        <div className="brand">
          <h1>LedgerAgent</h1>
          <span className="badge badge-neutral">OCR + Company Skills 實驗室 (TS)</span>
          {health ? (
            <span className="badge badge-ok">DB: {health.database}</span>
          ) : (
            <span className="badge badge-error">API 未連線</span>
          )}
        </div>

        <div className="controls">
          <label className="inline-control">
            目前操作公司：
            <select
              value={selectedCompanyId}
              onChange={(e) => setSelectedCompanyId(e.target.value)}
            >
              {companies.map((c) => (
                <option key={c.company_id} value={c.company_id}>
                  {c.name} ({c.company_id})
                </option>
              ))}
            </select>
          </label>

          <label className="inline-control">
            AI Provider：
            <select
              value={provider}
              onChange={(e) => setProvider(e.target.value as ProviderName)}
            >
              <option value="mock">mock (離線免費規則模擬)</option>
              <option value="gemini" disabled={!health?.available_providers?.gemini}>
                gemini {health?.available_providers?.gemini ? "" : "(未設 API Key)"}
              </option>
              <option value="openai" disabled={!health?.available_providers?.openai}>
                openai {health?.available_providers?.openai ? "" : "(未設 API Key)"}
              </option>
            </select>
          </label>
        </div>
      </header>

      <main className="layout">
        {/* 左欄：憑證輸入 + 憑證清單 + 即時 SKILL.md 編輯器 */}
        <section className="column">
          {errorMsg && <div className="alert alert-error">{errorMsg}</div>}
          {toastMsg && <div className="alert alert-ok">{toastMsg}</div>}

          <div className="card">
            <h2>1. 上傳憑證或使用範例測試</h2>
            <p className="hint">
              可上傳發票/收據圖片 (JPG/PNG/PDF)，或直接點選下方範例憑證快速測試 JSON 產出。
            </p>
            <input
              type="file"
              accept="image/*,application/pdf"
              disabled={busy}
              onChange={handleFileUpload}
            />
            <div className="btn-row">
              {SAMPLE_VOUCHERS.map((sample) => (
                <button
                  key={sample.filename}
                  disabled={busy}
                  onClick={() => void handleSampleVoucher(sample)}
                >
                  {sample.label}
                </button>
              ))}
            </div>
          </div>

          <div className="card">
            <h2>
              2. 編輯公司 SKILL.md
              {skillDetail && (
                <span className="badge badge-neutral">
                  hash: {skillDetail.skill_hash}
                </span>
              )}
            </h2>
            <p className="hint">
              試著修改規則（在 mock 模式下可加一行如 <code>星巴克 -&gt; 6123 不可扣抵</code>
              ），再點擊「儲存並重跑目前憑證」，立即觀察右側 JSON 變化！
            </p>
            <textarea
              className="skill-editor"
              value={skillDraftMd}
              onChange={(e) => {
                setSkillDraftMd(e.target.value);
                setSkillDirty(true);
              }}
            />
            <div className="btn-row">
              <button
                disabled={busy || !skillDirty}
                onClick={() => void handleSaveSkill(false)}
              >
                僅儲存 SKILL.md
              </button>
              <button
                className="primary"
                disabled={busy || !activeVoucher}
                onClick={() => void handleSaveSkill(true)}
              >
                儲存並用新 Skill 重跑目前憑證
              </button>
            </div>

            {skillDetail && (
              <>
                <h3>
                  合法會計科目表 ({skillDetail.skill.chart_of_accounts.length} 筆) · 歷史記憶 (
                  {skillDetail.skill.history_examples.length} 筆)
                </h3>
                <div className="coa-pills">
                  {skillDetail.skill.chart_of_accounts.map((acc) => (
                    <span key={acc.code} className="coa-pill" title={acc.description}>
                      {acc.code} {acc.name}
                    </span>
                  ))}
                </div>
              </>
            )}
          </div>

          <div className="card">
            <h2>3. 已入庫憑證紀錄 ({vouchers.length})</h2>
            <div className="voucher-list">
              {vouchers.length === 0 && (
                <div className="hint">尚無憑證，請從上方上傳或點選範例憑證。</div>
              )}
              {vouchers.map((v) => (
                <button
                  key={v.voucher_id}
                  className={`voucher-item ${
                    activeVoucher?.voucher_id === v.voucher_id ? "active" : ""
                  }`}
                  onClick={() => void handleSelectVoucher(v.voucher_id)}
                >
                  <div>
                    <strong>{v.vendor_name}</strong>
                    <div className="meta">
                      {v.company_id} · {v.voucher_number || "無編號"} · NT${v.total_amount}
                    </div>
                  </div>
                  <span className="badge badge-neutral">{v.runs_count} runs</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* 右欄：憑證解析 JSON + 歷次分錄 Run 快照對照 */}
        <section className="column">
          {!activeVoucher ? (
            <div className="card">
              <h2>尚未選擇憑證</h2>
              <p className="hint">
                請從左側點選「星巴克電子發票」範例或上傳發票圖檔，系統將立即顯示 OCR 結構化 JSON 與套用公司 Skill 後產出的會計分錄 JSON。
              </p>
            </div>
          ) : (
            <>
              <div className="card">
                <h2>
                  憑證詳情：{activeVoucher.extraction.vendor_name}
                  <span className="badge badge-neutral">
                    NT$ {activeVoucher.extraction.total_amount}
                  </span>
                </h2>
                <div className="btn-row">
                  {companies.map((c) => (
                    <button
                      key={c.company_id}
                      disabled={busy}
                      onClick={() => void handleRerunWithCompany(c.company_id)}
                    >
                      用「{c.name}」Skill 試跑這張憑證
                    </button>
                  ))}
                </div>

                {activeVoucher.file_url &&
                  !activeVoucher.file_url.toLowerCase().endsWith(".pdf") && (
                    <img
                      className="preview-img"
                      src={activeVoucher.file_url}
                      alt={activeVoucher.filename || "voucher"}
                    />
                  )}

                <details style={{ marginTop: 10 }}>
                  <summary style={{ cursor: "pointer", fontSize: "0.85rem", fontWeight: 600 }}>
                    檢視 Stage 1 OCR 結構化憑證 JSON (VoucherExtraction)
                  </summary>
                  <pre className="json-box">
                    {JSON.stringify(activeVoucher.extraction, null, 2)}
                  </pre>
                </details>
              </div>

              <div className="card">
                <h2>
                  分錄執行快照對照（共 {activeVoucher.runs.length} 次 Run，最新在前）
                  {activeRun && (
                    <button
                      className="success"
                      disabled={busy || activeRun.status === "approved" || !activeRun.is_valid}
                      onClick={() => void handleApproveRun(activeRun)}
                    >
                      {activeRun.status === "approved"
                        ? "已核准並寫入記憶庫"
                        : "核准並寫入 history.jsonl"}
                    </button>
                  )}
                </h2>

                <div className="runs-tabs">
                  {activeVoucher.runs.map((r, idx) => (
                    <button
                      key={r.run_id}
                      className={`run-tab ${idx === selectedRunIndex ? "active" : ""}`}
                      onClick={() => setSelectedRunIndex(idx)}
                    >
                      #{activeVoucher.runs.length - idx} {r.company_id} ({r.skill_hash.slice(0, 6)}) ·{" "}
                      {r.status}
                    </button>
                  ))}
                </div>

                {activeRun && (
                  <>
                    <div className="btn-row" style={{ marginBottom: 8 }}>
                      <span className="badge badge-neutral">公司: {activeRun.company_id}</span>
                      <span className="badge badge-neutral">
                        Provider: {activeRun.provider} ({activeRun.model_name})
                      </span>
                      <span className="badge badge-neutral">
                        Skill Hash: {activeRun.skill_hash}
                      </span>
                      <span
                        className={`badge ${
                          activeRun.is_valid ? "badge-ok" : "badge-error"
                        }`}
                      >
                        {activeRun.is_valid ? "會計規則檢核通過" : "有檢核 ERROR"}
                      </span>
                      <span className="badge badge-neutral">
                        進項可扣抵: {activeRun.journal_draft.vat_deductible ? "是" : "否"}
                      </span>
                    </div>

                    {activeRun.validation_issues.length > 0 && (
                      <div className="issue-list">
                        {activeRun.validation_issues.map((issue, i) => (
                          <div
                            key={`${issue.code}-${i}`}
                            className={`badge ${
                              issue.severity === "error" ? "badge-error" : "badge-warn"
                            }`}
                            style={{ borderRadius: 6, padding: "6px 10px" }}
                          >
                            [{issue.severity.toUpperCase()} / {issue.code}] {issue.message}
                          </div>
                        ))}
                      </div>
                    )}

                    <table className="journal-table">
                      <thead>
                        <tr>
                          <th>方向</th>
                          <th>科目代碼</th>
                          <th>科目名稱</th>
                          <th className="num">借方金額</th>
                          <th className="num">貸方金額</th>
                          <th>摘要</th>
                        </tr>
                      </thead>
                      <tbody>
                        {draftLines.map((line, i) => (
                          <tr key={i}>
                            <td>{line.side === "debit" ? "借 (Dr)" : "貸 (Cr)"}</td>
                            <td>
                              <code>{line.account_code}</code>
                            </td>
                            <td>{line.account_name}</td>
                            <td className="num">
                              {line.side === "debit" ? Number(line.amount).toLocaleString() : ""}
                            </td>
                            <td className="num">
                              {line.side === "credit" ? Number(line.amount).toLocaleString() : ""}
                            </td>
                            <td>{line.memo}</td>
                          </tr>
                        ))}
                      </tbody>
                      <tfoot>
                        <tr>
                          <th colSpan={3}>合計</th>
                          <th className="num">{totalDebit.toLocaleString()}</th>
                          <th className="num">{totalCredit.toLocaleString()}</th>
                          <th>
                            {totalDebit === totalCredit ? "借貸平衡" : "借貸不平衡！"}
                          </th>
                        </tr>
                      </tfoot>
                    </table>

                    <h3>AI 推理與引用規則</h3>
                    <p className="hint" style={{ color: "var(--text)" }}>
                      {activeRun.journal_draft.reasoning}
                    </p>
                    <div className="coa-pills">
                      {(activeRun.journal_draft.applied_rules || []).map((rule, idx) => (
                        <span key={idx} className="coa-pill">
                          {rule}
                        </span>
                      ))}
                      {activeRun.retrieved_example_ids.map((exId) => (
                        <span key={exId} className="coa-pill">
                          Few-Shot: {exId}
                        </span>
                      ))}
                    </div>

                    <h3>
                      完整分錄輸出 JSON（重點檢視區）
                      <button
                        style={{ marginLeft: 8, padding: "3px 8px", fontSize: "0.75rem" }}
                        onClick={() => {
                          void navigator.clipboard?.writeText(
                            JSON.stringify(activeRun, null, 2)
                          );
                          showToast("已複製完整 JSON 至剪貼簿！");
                        }}
                      >
                        複製 JSON
                      </button>
                    </h3>
                    <pre className="json-box">{JSON.stringify(activeRun, null, 2)}</pre>
                  </>
                )}
              </div>
            </>
          )}
        </section>
      </main>
    </div>
  );
}

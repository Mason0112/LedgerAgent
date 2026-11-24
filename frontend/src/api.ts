import type {
  CompanyProfile,
  HealthResponse,
  JournalRunResponse,
  ProviderName,
  SkillDetailResponse,
  VoucherDetailResponse,
  VoucherExtraction,
  VoucherSummaryResponse,
} from "./types";

const API_BASE = "";

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const errData = (await res.json()) as { detail?: unknown };
      message =
        typeof errData.detail === "string"
          ? errData.detail
          : JSON.stringify(errData.detail ?? errData);
    } catch {
      // ignore json parse error
    }
    throw new Error(message);
  }
  return (await res.json()) as T;
}

export const api = {
  health: (): Promise<HealthResponse> => request<HealthResponse>("/api/health"),

  listCompanies: (): Promise<CompanyProfile[]> =>
    request<CompanyProfile[]>("/api/companies"),

  getCompanySkill: (companyId: string): Promise<SkillDetailResponse> =>
    request<SkillDetailResponse>(`/api/companies/${companyId}/skill`),

  updateCompanySkill: (
    companyId: string,
    skillMarkdown: string
  ): Promise<SkillDetailResponse> =>
    request<SkillDetailResponse>(`/api/companies/${companyId}/skill`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ skill_markdown: skillMarkdown }),
    }),

  listVouchers: (companyId?: string): Promise<VoucherSummaryResponse[]> =>
    request<VoucherSummaryResponse[]>(
      companyId
        ? `/api/vouchers?company_id=${encodeURIComponent(companyId)}`
        : "/api/vouchers"
    ),

  getVoucher: (voucherId: string): Promise<VoucherDetailResponse> =>
    request<VoucherDetailResponse>(`/api/vouchers/${voucherId}`),

  uploadVoucher: (
    companyId: string,
    file: File,
    provider?: ProviderName
  ): Promise<VoucherDetailResponse> => {
    const form = new FormData();
    form.append("company_id", companyId);
    if (provider) form.append("provider", provider);
    form.append("file", file);
    return request<VoucherDetailResponse>("/api/vouchers/upload", {
      method: "POST",
      body: form,
    });
  },

  createFromJson: (
    companyId: string,
    extraction: VoucherExtraction,
    provider?: ProviderName,
    filename?: string
  ): Promise<VoucherDetailResponse> =>
    request<VoucherDetailResponse>("/api/vouchers/from-json", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_id: companyId,
        extraction,
        provider: provider ?? null,
        filename,
      }),
    }),

  rerunVoucher: (
    voucherId: string,
    companyId: string,
    provider?: ProviderName
  ): Promise<VoucherDetailResponse> =>
    request<VoucherDetailResponse>(`/api/vouchers/${voucherId}/rerun`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        company_id: companyId,
        provider: provider ?? null,
      }),
    }),

  approveRun: (
    voucherId: string,
    runId: string,
    saveToHistory = true
  ): Promise<JournalRunResponse> =>
    request<JournalRunResponse>(
      `/api/vouchers/${voucherId}/runs/${runId}/approve`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ save_to_history: saveToHistory }),
      }
    ),
};

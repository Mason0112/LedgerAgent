/**
 * 前後端共享型別契約（對應 backend/src/ledger_agent/models/ 中的 Pydantic v2 模型）。
 * 透過 TypeScript 嚴格型別檢查，確保前端控制與檢視的 JSON 結構與後端完全一致。
 */

export type ProviderName = "mock" | "gemini" | "openai";

export type VoucherType =
  | "triplicate_invoice"
  | "duplicate_invoice"
  | "electronic_invoice"
  | "receipt"
  | "other";

export type PaymentMethod =
  | "cash"
  | "bank_transfer"
  | "credit_card"
  | "petty_cash"
  | "unknown";

export type EntrySide = "debit" | "credit";

export type ValidationSeverity = "error" | "warning";

export type RunStatus = "draft" | "needs_review" | "approved";

export interface HealthResponse {
  status: string;
  database: string;
  default_provider: ProviderName;
  available_providers: Record<ProviderName, boolean>;
}

export interface CompanyProfile {
  company_id: string;
  name: string;
  tax_id: string;
  industry: string;
  currency: string;
  vat_rate: string | number;
  default_payment_account: string;
  capitalization_threshold: string | number;
  description: string;
}

export interface AccountItem {
  code: string;
  name: string;
  category: string;
  normal_side: string;
  description: string;
}

export interface VendorRule {
  rule_id: string;
  match_vendor_tax_id: string;
  match_keywords: string[];
  debit_account_code: string;
  credit_account_code: string | null;
  vat_deductible: boolean;
  note: string;
}

export interface HistoryExample {
  example_id: string;
  vendor_name: string;
  vendor_tax_id: string | null;
  voucher_type: string;
  items_summary: string;
  total_amount: string;
  entries: Array<Record<string, unknown>>;
  reasoning: string;
}

export interface CompanySkill {
  profile: CompanyProfile;
  skill_markdown: string;
  chart_of_accounts: AccountItem[];
  vendor_rules: VendorRule[];
  history_examples: HistoryExample[];
}

export interface SkillDetailResponse {
  skill_hash: string;
  skill: CompanySkill;
}

export interface VoucherLineItem {
  description: string;
  quantity: string | number;
  unit_price?: string | number | null;
  amount: string | number;
}

export interface VoucherExtraction {
  voucher_type: VoucherType;
  voucher_number?: string | null;
  voucher_date?: string | null;
  vendor_name: string;
  vendor_tax_id?: string | null;
  buyer_name?: string | null;
  buyer_tax_id?: string | null;
  currency: string;
  subtotal?: string | number | null;
  tax_amount?: string | number | null;
  total_amount: string | number;
  payment_method: PaymentMethod;
  items: VoucherLineItem[];
  notes?: string | null;
  confidence: number;
  raw_text?: string | null;
}

export interface JournalLine {
  side: EntrySide;
  account_code: string;
  account_name: string;
  amount: string | number;
  memo: string;
}

export interface JournalEntryDraft {
  entry_date: string;
  summary: string;
  vat_deductible: boolean;
  lines: JournalLine[];
  applied_rules: string[];
  reasoning: string;
  confidence: number;
}

export interface ValidationIssue {
  code: string;
  severity: ValidationSeverity;
  message: string;
}

export interface JournalRunResponse {
  run_id: string;
  voucher_id: string;
  company_id: string;
  provider: string;
  model_name: string;
  status: RunStatus;
  skill_hash: string;
  matched_rule_ids: string[];
  retrieved_example_ids: string[];
  journal_draft: JournalEntryDraft;
  validation_issues: ValidationIssue[];
  is_valid: boolean;
  created_at: string;
}

export interface VoucherSummaryResponse {
  voucher_id: string;
  company_id: string;
  filename: string | null;
  vendor_name: string;
  voucher_number: string | null;
  voucher_date: string | null;
  total_amount: string;
  latest_status: RunStatus;
  runs_count: number;
  created_at: string;
}

export interface VoucherDetailResponse {
  voucher_id: string;
  company_id: string;
  filename: string | null;
  file_url: string | null;
  extraction: VoucherExtraction;
  runs: JournalRunResponse[];
  created_at: string;
}

export interface SampleVoucherPreset {
  label: string;
  filename: string;
  extraction: VoucherExtraction;
}

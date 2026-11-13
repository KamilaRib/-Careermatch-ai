import type { ParsedResumeData } from "./resume";

export type ChangeType =
  | "reordenacao_competencias"
  | "alinhamento_resumo"
  | "destaque_experiencia"
  | "padronizacao_ats";

export interface OptimizationChangeItem {
  section: string;
  change_type: ChangeType;
  before: string;
  after: string;
  justification: string;
}

export interface KeywordSuggestionItem {
  keyword: string;
  importance: string;
  category: string;
  advisory_note: string;
}

export interface PreservationReport {
  zero_fabrication_verified: boolean;
  preserved_experiences_count: number;
  preserved_education_count: number;
  preserved_skills_count: number;
  preserved_certifications_count: number;
  blocked_fabrications: string[];
  verification_note: string;
}

export interface ATSResumeResult {
  optimized_data: ParsedResumeData;
  markdown_preview: string;
  plain_text_preview: string;
  changes: OptimizationChangeItem[];
  incorporated_keywords: string[];
  suggested_keywords: KeywordSuggestionItem[];
  preservation_report: PreservationReport;
  optimization_method: "llm" | "deterministic_fallback" | "deterministic";
  provider_used: string;
  provider_fallback_reason: string | null;
  approved: boolean;
}

export interface CurrentATSResumeResponse {
  has_ats_resume: boolean;
  result: ATSResumeResult | null;
}

export type ExportFormat = "pdf" | "docx" | "txt" | "md";

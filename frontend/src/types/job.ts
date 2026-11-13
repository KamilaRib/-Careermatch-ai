import type { EvidenceValidationReport, ExtractionMethod } from "@/types/resume";

export type RequirementImportance = "obrigatorio" | "desejavel" | "contextual" | "nao_especificado";

export type RequirementCategory =
  | "competencias_tecnicas"
  | "experiencia_profissional"
  | "formacao_certificacoes"
  | "competencias_comportamentais"
  | "idiomas"
  | "outros";

export interface JobRequirementItem {
  name: string;
  category: RequirementCategory;
  importance: RequirementImportance;
  is_eliminatory: boolean;
  min_years?: number | null;
  evidence_quote: string;
  evidence_verified: boolean;
}

export interface ParsedJobData {
  title: string;
  company: string;
  location: string;
  work_model: string;
  seniority: string;
  experience_years_required: string;
  education_required: string;
  responsibilities: string[];
  requirements: JobRequirementItem[];
  technologies: string[];
  languages: string[];
  keywords: string[];
}

export interface JobSessionState {
  has_job: boolean;
  source_kind: "pasted" | "url" | "manual" | null;
  source_url: string | null;
  raw_text: string;
  data: ParsedJobData | null;
  extraction_method: ExtractionMethod | null;
  provider_used: string | null;
  provider_fallback_reason: string | null;
  evidence_report: EvidenceValidationReport;
  confirmed: boolean;
}

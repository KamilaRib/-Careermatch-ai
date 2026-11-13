export interface PersonalInfo {
  full_name: string;
  email: string;
  phone: string;
  linkedin: string;
  location: string;
  evidence_quote: string;
}

export interface ExperienceItem {
  role: string;
  company: string;
  period: string;
  location: string;
  responsibilities: string[];
  achievements: string[];
  evidence_quote: string;
  evidence_verified: boolean;
}

export interface EducationItem {
  degree: string;
  institution: string;
  period: string;
  evidence_quote: string;
  evidence_verified: boolean;
}

export interface CertificationItem {
  name: string;
  issuer: string;
  year: string;
  evidence_quote: string;
  evidence_verified: boolean;
}

export interface SkillItem {
  name: string;
  category: string;
  evidence_quote: string;
  evidence_verified: boolean;
}

export interface LanguageItem {
  language: string;
  proficiency: string;
  evidence_quote: string;
  evidence_verified: boolean;
}

export interface ProjectItem {
  name: string;
  description: string;
  technologies: string[];
  url: string;
  evidence_quote: string;
  evidence_verified: boolean;
}

export interface ParsedResumeData {
  personal_info: PersonalInfo;
  professional_summary: string;
  summary_evidence_quote: string;
  experiences: ExperienceItem[];
  education: EducationItem[];
  certifications: CertificationItem[];
  technical_skills: SkillItem[];
  languages: LanguageItem[];
  projects: ProjectItem[];
}

export interface EvidenceValidationReport {
  total_items_checked: number;
  verified_items: number;
  unverified_warnings: string[];
}

export type ExtractionMethod = "llm" | "deterministic_fallback";

export interface ResumeUploadResponse {
  filename: string;
  kind: "pdf" | "docx" | "txt";
  size_bytes: number;
  char_count: number;
  raw_text: string;
}

export interface ResumeSessionState {
  has_resume: boolean;
  filename: string | null;
  source_kind: "pdf" | "docx" | "txt" | "pasted" | null;
  raw_text: string;
  data: ParsedResumeData | null;
  extraction_method: ExtractionMethod | null;
  provider_used: string | null;
  provider_fallback_reason: string | null;
  evidence_report: EvidenceValidationReport;
  confirmed: boolean;
}

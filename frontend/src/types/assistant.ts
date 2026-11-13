export type AssistantMessageRole = "user" | "assistant";

export type AssistantTopic =
  | "compatibilidade"
  | "lacunas"
  | "melhorias"
  | "entrevista"
  | "candidatura"
  | "geral";

export interface AssistantCitation {
  source: "curriculo" | "vaga" | "matching" | "ats";
  label: string;
  evidence: string;
}

export interface AssistantChatMessage {
  id: string;
  role: AssistantMessageRole;
  content: string;
  created_at: string;
  citations: AssistantCitation[];
  response_method: "llm" | "deterministic_fallback" | "deterministic" | null;
  provider_used: string | null;
  provider_fallback_reason: string | null;
}

export interface AssistantContextSummary {
  has_resume: boolean;
  resume_confirmed: boolean;
  candidate_name: string;
  has_job: boolean;
  job_confirmed: boolean;
  job_title: string;
  has_matching: boolean;
  overall_score: number | null;
  band_label: string | null;
  has_ats_resume: boolean;
  verified_skills: string[];
  unverified_requirements: string[];
}

export interface AssistantChatResponse {
  reply: AssistantChatMessage;
  history: AssistantChatMessage[];
  context_summary: AssistantContextSummary;
}

export interface AssistantSessionState {
  history: AssistantChatMessage[];
  context_summary: AssistantContextSummary;
  suggested_prompts: string[];
}


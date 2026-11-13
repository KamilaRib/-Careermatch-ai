export type MatchState =
  | "atendido"
  | "parcialmente_atendido"
  | "nao_identificado"
  | "nao_atendido"
  | "nao_avaliavel";

export type ScoreBand =
  | "baixa_compatibilidade"
  | "compatibilidade_parcial"
  | "boa_compatibilidade"
  | "alta_compatibilidade";

export type ScoringCategoryKey =
  | "competencias_tecnicas"
  | "experiencia_profissional"
  | "requisitos_obrigatorios"
  | "formacao_certificacoes"
  | "competencias_comportamentais"
  | "palavras_chave";

export interface RequirementMatchItem {
  requirement_name: string;
  category: ScoringCategoryKey;
  importance: string;
  is_eliminatory: boolean;
  state: MatchState;
  credit: number;
  job_evidence: string;
  resume_evidence: string;
  explanation: string;
}

export interface CategoryScoreItem {
  key: ScoringCategoryKey;
  label: string;
  base_weight_pct: number;
  normalized_weight_pct: number;
  applicable: boolean;
  score: number;
  weighted_contribution: number;
  evaluated_count: number;
  matched_count: number;
  partial_count: number;
}

export interface MatchingResult {
  overall_score: number;
  band: ScoreBand;
  band_label: string;
  category_scores: CategoryScoreItem[];
  requirement_matches: RequirementMatchItem[];
  matched_keywords: string[];
  partial_keywords: string[];
  unverified_requirements: string[];
  eliminatory_alerts: string[];
  strengths: string[];
  gaps: string[];
  recommendations: string[];
  methodology_note: string;
}

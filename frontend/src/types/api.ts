export interface HealthResponse {
  status: "ok";
  version: string;
  environment: string;
  ai_provider: string;
  ai_configured: boolean;
  ai_key_warning?: string | null;
}

export interface SessionInfo {
  active: boolean;
  ttl_minutes: number;
}

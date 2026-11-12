export interface HealthResponse {
  status: "ok";
  version: string;
  environment: string;
  ai_provider: string;
  ai_configured: boolean;
}

export interface SessionInfo {
  active: boolean;
  ttl_minutes: number;
}

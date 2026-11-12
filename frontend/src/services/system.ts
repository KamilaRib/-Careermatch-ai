import { api } from "@/lib/api";
import type { HealthResponse, SessionInfo } from "@/types/api";

export const systemService = {
  health: () => api<HealthResponse>("/health"),
  session: () => api<SessionInfo>("/sessions/current"),
  deleteSession: () => api<{ deleted: boolean }>("/sessions/current", { method: "DELETE" }),
};

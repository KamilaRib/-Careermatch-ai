import { api } from "@/lib/api";
import type { JobSessionState, ParsedJobData } from "@/types/job";

export const jobService = {
  getCurrent: () => api<JobSessionState>("/jobs/current"),

  parseText: (params: { text: string; use_deterministic_only?: boolean }) =>
    api<JobSessionState>("/jobs/parse", {
      method: "POST",
      json: params,
    }),

  extractUrl: (params: { url: string; parse_immediately?: boolean; use_deterministic_only?: boolean }) =>
    api<JobSessionState>("/jobs/extract-url", {
      method: "POST",
      json: params,
    }),

  confirm: (data: ParsedJobData, confirmed = true, raw_text?: string) =>
    api<JobSessionState>("/jobs/current", {
      method: "PUT",
      json: { data, confirmed, raw_text },
    }),
};

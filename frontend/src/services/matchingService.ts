import { api } from "@/lib/api";
import type { MatchingResult } from "@/types/matching";

export const matchingService = {
  getCurrent: () => api<MatchingResult | null>("/matching/current"),

  analyze: () =>
    api<MatchingResult>("/matching/analyze", {
      method: "POST",
    }),
};

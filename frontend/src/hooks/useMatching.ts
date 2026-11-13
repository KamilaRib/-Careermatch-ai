import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { matchingService } from "@/services/matchingService";

const MATCHING_QUERY_KEY = ["matching", "current"] as const;

export function useCurrentMatching() {
  return useQuery({
    queryKey: MATCHING_QUERY_KEY,
    queryFn: matchingService.getCurrent,
  });
}

export function useAnalyzeMatching() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: matchingService.analyze,
    onSuccess: (result) => {
      qc.setQueryData(MATCHING_QUERY_KEY, result);
    },
  });
}

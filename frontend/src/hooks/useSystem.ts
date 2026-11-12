import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { systemService } from "@/services/system";

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: systemService.health,
    refetchInterval: 60_000,
    retry: 1,
  });
}

export function useDeleteSession() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: systemService.deleteSession,
    onSuccess: () => qc.clear(),
  });
}

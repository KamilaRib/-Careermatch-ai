import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { jobService } from "@/services/jobService";
import type { ParsedJobData } from "@/types/job";

const JOB_QUERY_KEY = ["job", "current"] as const;

export function useCurrentJob() {
  return useQuery({
    queryKey: JOB_QUERY_KEY,
    queryFn: jobService.getCurrent,
  });
}

export function useParseJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { text: string; use_deterministic_only?: boolean }) =>
      jobService.parseText(params),
    onSuccess: (state) => {
      qc.setQueryData(JOB_QUERY_KEY, state);
    },
  });
}

export function useExtractJobUrl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params: { url: string; parse_immediately?: boolean; use_deterministic_only?: boolean }) =>
      jobService.extractUrl(params),
    onSuccess: (state) => {
      qc.setQueryData(JOB_QUERY_KEY, state);
    },
  });
}

export function useConfirmJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      data,
      confirmed = true,
      raw_text,
    }: {
      data: ParsedJobData;
      confirmed?: boolean;
      raw_text?: string;
    }) => jobService.confirm(data, confirmed, raw_text),
    onSuccess: (state) => {
      qc.setQueryData(JOB_QUERY_KEY, state);
    },
  });
}

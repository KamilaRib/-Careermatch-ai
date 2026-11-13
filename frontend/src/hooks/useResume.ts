import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { resumeService } from "@/services/resumeService";
import type { ParsedResumeData } from "@/types/resume";

const RESUME_QUERY_KEY = ["resume", "current"] as const;

export function useCurrentResume() {
  return useQuery({
    queryKey: RESUME_QUERY_KEY,
    queryFn: resumeService.getCurrent,
  });
}

export function useUploadResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => resumeService.uploadFile(file),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: RESUME_QUERY_KEY });
    },
  });
}

export function useParseResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (params?: { text?: string; use_deterministic_only?: boolean }) =>
      resumeService.parse(params),
    onSuccess: (state) => {
      qc.setQueryData(RESUME_QUERY_KEY, state);
    },
  });
}

export function useConfirmResume() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ data, confirmed = true }: { data: ParsedResumeData; confirmed?: boolean }) =>
      resumeService.confirm(data, confirmed),
    onSuccess: (state) => {
      qc.setQueryData(RESUME_QUERY_KEY, state);
    },
  });
}

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import {
  generateATSResume,
  getCurrentATSResume,
  updateAndApproveATSResume,
} from "@/services/atsResumeService";
import { jobService } from "@/services/jobService";
import { resumeService } from "@/services/resumeService";
import type { ATSResumeResult } from "@/types/atsResume";
import type { ParsedResumeData } from "@/types/resume";

export function useATSResume() {
  const [result, setResult] = useState<ATSResumeResult | null>(null);
  const [resumeConfirmed, setResumeConfirmed] = useState(false);
  const [jobConfirmed, setJobConfirmed] = useState(false);
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const loadInitial = useCallback(async () => {
    setIsLoadingStatus(true);
    try {
      const [resState, jobState, currentATS] = await Promise.all([
        resumeService.getCurrent().catch(() => null),
        jobService.getCurrent().catch(() => null),
        getCurrentATSResume().catch(() => null),
      ]);
      setResumeConfirmed(Boolean(resState?.has_resume && resState?.confirmed));
      setJobConfirmed(Boolean(jobState?.has_job && jobState?.confirmed));
      if (currentATS?.has_ats_resume && currentATS.result) {
        setResult(currentATS.result);
      }
    } finally {
      setIsLoadingStatus(false);
    }
  }, []);

  useEffect(() => {
    void loadInitial();
  }, [loadInitial]);

  const generate = useCallback(async (useDeterministicOnly = false) => {
    setIsGenerating(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const res = await generateATSResume(useDeterministicOnly);
      setResult(res);
      setSuccessMessage(
        "Versão otimizada para ATS gerada! Revise as alterações e aprove para liberar a exportação.",
      );
      return res;
    } catch (err: unknown) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "Não foi possível gerar o currículo ATS otimizado.";
      setError(msg);
      return null;
    } finally {
      setIsGenerating(false);
    }
  }, []);

  const saveAndApprove = useCallback(
    async (optimizedData: ParsedResumeData, approved = true) => {
      setIsSaving(true);
      setError(null);
      setSuccessMessage(null);
      try {
        const res = await updateAndApproveATSResume(optimizedData, approved);
        setResult(res);
        setSuccessMessage(
          approved
            ? "Currículo otimizado aprovado! Os botões de exportação (PDF, DOCX, TXT e Markdown) estão liberados."
            : "Edições salvas no rascunho ATS.",
        );
        return res;
      } catch (err: unknown) {
        const msg =
          err instanceof ApiError
            ? err.message
            : "Não foi possível salvar e aprovar o currículo otimizado.";
        setError(msg);
        return null;
      } finally {
        setIsSaving(false);
      }
    },
    [],
  );

  return {
    result,
    resumeConfirmed,
    jobConfirmed,
    isLoadingStatus,
    isGenerating,
    isSaving,
    error,
    successMessage,
    generate,
    saveAndApprove,
  };
}

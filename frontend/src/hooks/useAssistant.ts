import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { assistantService } from "@/services/assistantService";
import type {
  AssistantChatMessage,
  AssistantContextSummary,
  AssistantTopic,
} from "@/types/assistant";

const EMPTY_CONTEXT: AssistantContextSummary = {
  has_resume: false,
  resume_confirmed: false,
  candidate_name: "",
  has_job: false,
  job_confirmed: false,
  job_title: "",
  has_matching: false,
  overall_score: null,
  band_label: null,
  has_ats_resume: false,
  verified_skills: [],
  unverified_requirements: [],
};

export function useAssistant() {
  const [history, setHistory] = useState<AssistantChatMessage[]>([]);
  const [contextSummary, setContextSummary] =
    useState<AssistantContextSummary>(EMPTY_CONTEXT);
  const [suggestedPrompts, setSuggestedPrompts] = useState<string[]>([]);
  const [isLoadingState, setIsLoadingState] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadState = useCallback(async () => {
    setIsLoadingState(true);
    try {
      const state = await assistantService.getState();
      setHistory(state.history ?? []);
      setContextSummary(state.context_summary ?? EMPTY_CONTEXT);
      setSuggestedPrompts(state.suggested_prompts ?? []);
    } catch {
      /* keep default state */
    } finally {
      setIsLoadingState(false);
    }
  }, []);

  useEffect(() => {
    void loadState();
  }, [loadState]);

  const sendMessage = useCallback(
    async (
      message: string,
      topic: AssistantTopic = "geral",
      useDeterministicOnly = false,
    ) => {
      const trimmed = message.trim();
      if (trimmed.length < 2) {
        setError("Digite uma pergunta com pelo menos 2 caracteres.");
        return null;
      }
      setIsSending(true);
      setError(null);
      try {
        const res = await assistantService.sendMessage({
          message: trimmed,
          topic,
          use_deterministic_only: useDeterministicOnly,
        });
        setHistory(res.history);
        setContextSummary(res.context_summary);
        return res;
      } catch (err: unknown) {
        const msg =
          err instanceof ApiError
            ? err.message
            : "Não foi possível enviar sua mensagem ao assistente.";
        setError(msg);
        return null;
      } finally {
        setIsSending(false);
      }
    },
    [],
  );

  const clearHistory = useCallback(async () => {
    setError(null);
    try {
      const state = await assistantService.clearHistory();
      setHistory(state.history ?? []);
      setContextSummary(state.context_summary ?? EMPTY_CONTEXT);
    } catch (err: unknown) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "Não foi possível limpar o histórico do assistente.";
      setError(msg);
    }
  }, []);

  return {
    history,
    contextSummary,
    suggestedPrompts,
    isLoadingState,
    isSending,
    error,
    sendMessage,
    clearHistory,
    reload: loadState,
  };
}


import { api } from "@/lib/api";
import type {
  AssistantChatResponse,
  AssistantSessionState,
  AssistantTopic,
} from "@/types/assistant";

export const assistantService = {
  getState: () => api<AssistantSessionState>("/assistant/current"),

  sendMessage: (params: {
    message: string;
    topic?: AssistantTopic;
    use_deterministic_only?: boolean;
  }) =>
    api<AssistantChatResponse>("/assistant/chat", {
      method: "POST",
      json: {
        message: params.message,
        topic: params.topic ?? "geral",
        use_deterministic_only: params.use_deterministic_only ?? false,
      },
    }),

  clearHistory: () =>
    api<AssistantSessionState>("/assistant/history", {
      method: "DELETE",
    }),
};


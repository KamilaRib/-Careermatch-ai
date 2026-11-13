import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { json, mockFetch, renderRoute } from "@/test/utils";
import type { AssistantChatResponse, AssistantSessionState } from "@/types/assistant";

const healthy = {
  status: "ok",
  version: "0.1.0",
  environment: "test",
  ai_provider: "ollama",
  ai_configured: true,
  ai_key_warning: null,
};

const emptyState: AssistantSessionState = {
  history: [],
  context_summary: {
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
  },
  suggested_prompts: [
    "Qual é a minha compatibilidade atual com a vaga e quais são meus principais pontos fortes?",
  ],
};

const activeState: AssistantSessionState = {
  history: [],
  context_summary: {
    has_resume: true,
    resume_confirmed: true,
    candidate_name: "Ana Carolina Mendes",
    has_job: true,
    job_confirmed: true,
    job_title: "Pessoa Desenvolvedora Backend Python Sênior",
    has_matching: true,
    overall_score: 77,
    band_label: "Boa compatibilidade",
    has_ats_resume: true,
    verified_skills: ["Python", "FastAPI", "PostgreSQL", "Docker"],
    unverified_requirements: ["Kubernetes", "Kafka"],
  },
  suggested_prompts: [
    "Quais requisitos da vaga não foram identificados no meu currículo e como devo lidar com eles?",
  ],
};

describe("AssistantPage (Fase 6)", () => {
  beforeEach(() => {
    document.cookie = "cm_csrf=test_csrf_token; path=/";
  });

  it("alerts the user when resume and job are missing from the session", async () => {
    mockFetch((url) => {
      if (url.endsWith("/health")) return json(healthy);
      if (url.endsWith("/assistant/current")) return json(emptyState);
      return json(healthy);
    });

    renderRoute("/assistente");
    expect(
      await screen.findByText(/carregue e confirme seu currículo e a vaga/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /ir para \/curriculo/i })).toHaveAttribute(
      "href",
      "/curriculo",
    );
  });

  it("sends a contextual question, displays the grounded reply with citations and preserves the ATS score", async () => {
    mockFetch((url, init) => {
      if (url.endsWith("/health")) return json(healthy);
      if (url.endsWith("/assistant/current")) return json(activeState);
      if (url.endsWith("/assistant/chat") && init?.method === "POST") {
        const resp: AssistantChatResponse = {
          reply: {
            id: "msg-2",
            role: "assistant",
            content:
              "Seu currículo comprova Python, FastAPI, PostgreSQL e Docker (Score ATS: 77%). Os requisitos Kubernetes e Kafka não foram identificados no documento.",
            created_at: new Date().toISOString(),
            citations: [
              {
                source: "matching",
                label: "Score Determinístico ATS: 77% (Boa compatibilidade)",
                evidence: "Comprovados: Python, FastAPI | Não identificados: Kubernetes, Kafka",
              },
            ],
            response_method: "llm",
            provider_used: "ollama:llama3.2",
            provider_fallback_reason: null,
          },
          history: [
            {
              id: "msg-1",
              role: "user",
              content: "Quais requisitos faltam e como me preparar?",
              created_at: new Date().toISOString(),
              citations: [],
              response_method: null,
              provider_used: null,
              provider_fallback_reason: null,
            },
            {
              id: "msg-2",
              role: "assistant",
              content:
                "Seu currículo comprova Python, FastAPI, PostgreSQL e Docker (Score ATS: 77%). Os requisitos Kubernetes e Kafka não foram identificados no documento.",
              created_at: new Date().toISOString(),
              citations: [
                {
                  source: "matching",
                  label: "Score Determinístico ATS: 77% (Boa compatibilidade)",
                  evidence: "Comprovados: Python, FastAPI | Não identificados: Kubernetes, Kafka",
                },
              ],
              response_method: "llm",
              provider_used: "ollama:llama3.2",
              provider_fallback_reason: null,
            },
          ],
          context_summary: activeState.context_summary,
        };
        return json(resp);
      }
      return json(healthy);
    });

    renderRoute("/assistente");
    expect(await screen.findByTestId("assistant-context-score")).toHaveTextContent("77%");

    const input = screen.getByPlaceholderText(/como posso explicar na entrevista/i);
    await userEvent.click(input);
    await userEvent.paste("Quais requisitos faltam e como me preparar?");
    await userEvent.click(screen.getByRole("button", { name: /enviar pergunta/i }));

    expect(await screen.findByTestId("assistant-chat-history")).toHaveTextContent(
      "Os requisitos Kubernetes e Kafka não foram identificados no documento.",
    );
    expect(screen.getByText(/referências aos dados da sessão/i)).toBeInTheDocument();
    expect(screen.getByTestId("assistant-context-score")).toHaveTextContent("77%");
  });
});


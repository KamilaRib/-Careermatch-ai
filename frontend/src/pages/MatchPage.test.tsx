import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { json, mockFetch, renderRoute } from "@/test/utils";
import type { MatchingResult } from "@/types/matching";

const healthy = {
  status: "ok",
  version: "0.1.0",
  environment: "test",
  ai_provider: "ollama",
  ai_configured: true,
  ai_key_warning: null,
};

const sampleMatching: MatchingResult = {
  overall_score: 82,
  band: "alta_compatibilidade",
  band_label: "Alta compatibilidade",
  category_scores: [
    {
      key: "competencias_tecnicas",
      label: "Competências técnicas",
      base_weight_pct: 30,
      normalized_weight_pct: 54.55,
      applicable: true,
      score: 85,
      weighted_contribution: 46.37,
      evaluated_count: 4,
      matched_count: 3,
      partial_count: 1,
    },
    {
      key: "experiencia_profissional",
      label: "Experiência profissional",
      base_weight_pct: 25,
      normalized_weight_pct: 45.45,
      applicable: true,
      score: 78,
      weighted_contribution: 35.45,
      evaluated_count: 2,
      matched_count: 1,
      partial_count: 1,
    },
  ],
  requirement_matches: [
    {
      requirement_name: "Python e FastAPI",
      category: "competencias_tecnicas",
      importance: "obrigatorio",
      is_eliminatory: false,
      state: "atendido",
      credit: 1.0,
      job_evidence: "- Domínio de Python e FastAPI",
      resume_evidence: "Competência: Python, FastAPI",
      explanation: "Competência comprovada diretamente no currículo (fastapi, python).",
    },
    {
      requirement_name: "Kafka",
      category: "competencias_tecnicas",
      importance: "desejavel",
      is_eliminatory: false,
      state: "nao_identificado",
      credit: 0.0,
      job_evidence: "- Experiência com mensageria Kafka",
      resume_evidence: "",
      explanation: "Não identificado no texto do currículo.",
    },
  ],
  matched_keywords: ["Python e FastAPI", "PostgreSQL", "Docker"],
  partial_keywords: ["Kubernetes"],
  unverified_requirements: ["Kafka"],
  eliminatory_alerts: [],
  strengths: ["Python e FastAPI: Competência comprovada diretamente no currículo."],
  gaps: ["Kafka (desejavel): Não identificado no texto do currículo."],
  recommendations: [
    "Utilize o gerador de Currículo ATS para alinhar a terminologia das suas experiências reais.",
  ],
  methodology_note: "Estimativa técnica determinística.",
};

describe("MatchPage (Fase 4)", () => {
  beforeEach(() => {
    document.cookie = "cm_csrf=test_csrf_token; path=/";
  });

  it("prompts the user to confirm resume and job when they are not confirmed yet", async () => {
    mockFetch((url) => {
      if (url.endsWith("/health")) return json(healthy);
      if (url.endsWith("/resumes/current")) return json({ has_resume: false, confirmed: false });
      if (url.endsWith("/jobs/current")) return json({ has_job: false, confirmed: false });
      if (url.endsWith("/matching/current")) return json(null);
      return json(healthy);
    });

    renderRoute("/compatibilidade");
    expect(
      await screen.findByText(/confirme o currículo e a vaga antes de iniciar o matching/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /calcular compatibilidade/i })).toBeDisabled();
  });

  it("calculates matching and renders score, categories, requirement states and CTA to ATS optimizer", async () => {
    let currentMatch: MatchingResult | null = null;
    mockFetch((url, init) => {
      if (url.endsWith("/health")) return json(healthy);
      if (url.endsWith("/resumes/current")) return json({ has_resume: true, confirmed: true });
      if (url.endsWith("/jobs/current")) return json({ has_job: true, confirmed: true });
      if (url.endsWith("/matching/current")) return json(currentMatch);
      if (url.endsWith("/matching/analyze") && init?.method === "POST") {
        currentMatch = sampleMatching;
        return json(sampleMatching);
      }
      return json(healthy);
    });

    renderRoute("/compatibilidade");
    const btn = await screen.findByRole("button", { name: /calcular compatibilidade/i });
    await waitFor(() => expect(btn).toBeEnabled());
    await userEvent.click(btn);

    expect(await screen.findByTestId("overall-score")).toHaveTextContent("82%");
    expect(screen.getByText("Alta compatibilidade")).toBeInTheDocument();
    expect(screen.getByText(/não identificado no currículo/i)).toBeInTheDocument();
    expect(
      screen.getAllByRole("link", { name: /gerar currículo otimizado para esta vaga/i })[0],
    ).toHaveAttribute("href", "/curriculo-ats");
  });
});

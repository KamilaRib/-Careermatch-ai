import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { json, mockFetch, renderRoute } from "@/test/utils";
import type { ATSResumeResult } from "@/types/atsResume";

const healthy = {
  status: "ok",
  version: "0.1.0",
  environment: "test",
  ai_provider: "ollama",
  ai_configured: true,
  ai_key_warning: null,
};

const sampleATSResult: ATSResumeResult = {
  optimized_data: {
    personal_info: {
      full_name: "Ana Carolina Mendes",
      email: "ana.mendes@email.com",
      phone: "(11) 98765-4321",
      linkedin: "linkedin.com/in/anacarolinamendes",
      location: "São Paulo - SP",
      evidence_quote: "Ana Carolina Mendes",
    },
    professional_summary:
      "Engenheira de Software Backend com 6 anos de experiência em Python e FastAPI. Competências comprovadas alinhadas à vaga: Python, FastAPI, PostgreSQL, Docker.",
    summary_evidence_quote: "Engenheira de Software Backend",
    experiences: [
      {
        role: "Engenheira Backend Sênior",
        company: "TechNova Soluções",
        period: "2022 - Atual",
        location: "São Paulo",
        responsibilities: ["Desenvolvimento de APIs REST em Python e FastAPI."],
        achievements: [],
        evidence_quote: "Engenheira Backend Sênior",
        evidence_verified: true,
      },
    ],
    education: [
      {
        degree: "Bacharelado em Ciência da Computação",
        institution: "Universidade de São Paulo",
        period: "2015 - 2018",
        evidence_quote: "Bacharelado em Ciência da Computação",
        evidence_verified: true,
      },
    ],
    certifications: [],
    technical_skills: [
      { name: "Python", category: "Técnica", evidence_quote: "Python", evidence_verified: true },
      { name: "FastAPI", category: "Técnica", evidence_quote: "FastAPI", evidence_verified: true },
      {
        name: "PostgreSQL",
        category: "Técnica",
        evidence_quote: "PostgreSQL",
        evidence_verified: true,
      },
    ],
    languages: [{ language: "Inglês", proficiency: "Avançado", evidence_quote: "Inglês", evidence_verified: true }],
    projects: [],
  },
  markdown_preview: "# Ana Carolina Mendes\n\n## Resumo Profissional\nEngenheira de Software Backend...",
  plain_text_preview:
    "Ana Carolina Mendes\nSão Paulo - SP | ana.mendes@email.com\n\nRESUMO PROFISSIONAL\nEngenheira de Software Backend com 6 anos de experiência em Python e FastAPI.",
  changes: [
    {
      section: "Competências Técnicas",
      change_type: "reordenacao_competencias",
      before: "Git, Python, FastAPI, PostgreSQL",
      after: "Python, FastAPI, PostgreSQL, Git",
      justification:
        "Competências comprovadas do candidato que correspondem diretamente aos requisitos da vaga foram posicionadas no início.",
    },
  ],
  incorporated_keywords: ["Python", "FastAPI", "PostgreSQL"],
  suggested_keywords: [
    {
      keyword: "Kubernetes",
      importance: "desejavel",
      category: "competencias_tecnicas",
      advisory_note:
        "Não adicionado automaticamente ao currículo (sem evidência no documento original).",
    },
  ],
  preservation_report: {
    zero_fabrication_verified: true,
    preserved_experiences_count: 1,
    preserved_education_count: 1,
    preserved_skills_count: 3,
    preserved_certifications_count: 0,
    blocked_fabrications: [],
    verification_note:
      "100% dos cargos, empresas, períodos, formações, certificações e competências foram validados contra o currículo original confirmado.",
  },
  optimization_method: "llm",
  provider_used: "ollama:llama3.2",
  provider_fallback_reason: null,
  approved: false,
};

describe("OptimizePage (Fase 5)", () => {
  beforeEach(() => {
    document.cookie = "cm_csrf=test_csrf_token; path=/";
  });

  it("disables generation when resume or job is not confirmed", async () => {
    mockFetch((url) => {
      if (url.endsWith("/health")) return json(healthy);
      if (url.endsWith("/resumes/current")) return json({ has_resume: false, confirmed: false });
      if (url.endsWith("/jobs/current")) return json({ has_job: false, confirmed: false });
      if (url.endsWith("/ats-resume/current")) return json({ has_ats_resume: false, result: null });
      return json(healthy);
    });

    renderRoute("/curriculo-ats");
    expect(
      await screen.findByText(/confirme o currículo e a vaga antes de gerar o currículo ats/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /gerar currículo ats/i })).toBeDisabled();
  });

  it("generates ATS resume, displays changelog and advisory keywords, and enables export after human approval", async () => {
    let currentATS: ATSResumeResult | null = null;
    mockFetch((url, init) => {
      if (url.endsWith("/health")) return json(healthy);
      if (url.endsWith("/resumes/current")) return json({ has_resume: true, confirmed: true });
      if (url.endsWith("/jobs/current")) return json({ has_job: true, confirmed: true });
      if (url.endsWith("/ats-resume/current") && (!init?.method || init.method === "GET")) {
        return json({ has_ats_resume: Boolean(currentATS), result: currentATS });
      }
      if (url.endsWith("/ats-resume/generate") && init?.method === "POST") {
        currentATS = sampleATSResult;
        return json(sampleATSResult);
      }
      if (url.endsWith("/ats-resume/current") && init?.method === "PUT") {
        currentATS = { ...sampleATSResult, approved: true };
        return json(currentATS);
      }
      return json(healthy);
    });

    renderRoute("/curriculo-ats");
    const genBtn = await screen.findByRole("button", { name: /gerar currículo ats/i });
    await waitFor(() => expect(genBtn).toBeEnabled());
    await userEvent.click(genBtn);

    expect(
      await screen.findByText(/garantia anti-alucinação: preservação factual verificada/i),
    ).toBeInTheDocument();
    expect(screen.getByTestId("ats-plain-preview")).toHaveTextContent("RESUMO PROFISSIONAL");
    expect(screen.getByText("Kubernetes")).toBeInTheDocument();

    // Before approval, export buttons are disabled
    expect(screen.getByRole("button", { name: /exportar pdf/i })).toBeDisabled();

    // Click human approval button
    const approveBtn = screen.getByRole("button", {
      name: /aprovar currículo otimizado para exportação/i,
    });
    await userEvent.click(approveBtn);

    expect(await screen.findByTestId("approval-badge")).toHaveTextContent("Aprovado pelo usuário");
    expect(screen.getByRole("link", { name: /exportar pdf/i })).toHaveAttribute(
      "href",
      "/api/v1/ats-resume/export/pdf",
    );
    expect(screen.getByRole("link", { name: /exportar docx/i })).toHaveAttribute(
      "href",
      "/api/v1/ats-resume/export/docx",
    );
  });
});

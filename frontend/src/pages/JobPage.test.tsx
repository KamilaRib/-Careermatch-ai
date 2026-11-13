import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { json, mockFetch, renderRoute } from "@/test/utils";
import type { JobSessionState } from "@/types/job";

const healthy = {
  status: "ok",
  version: "0.1.0",
  environment: "test",
  ai_provider: "ollama",
  ai_configured: true,
  ai_key_warning: null,
};

const emptyJob: JobSessionState = {
  has_job: false,
  source_kind: null,
  source_url: null,
  raw_text: "",
  data: null,
  extraction_method: null,
  provider_used: null,
  provider_fallback_reason: null,
  evidence_report: { total_items_checked: 0, verified_items: 0, unverified_warnings: [] },
  confirmed: false,
};

const parsedJob: JobSessionState = {
  has_job: true,
  source_kind: "pasted",
  source_url: null,
  raw_text: "Engenheiro Backend Sênior | FinPay\nRequisitos Obrigatórios:\n- Python e FastAPI\nDiferenciais:\n- Kubernetes",
  data: {
    title: "Engenheiro Backend Sênior",
    company: "FinPay",
    location: "São Paulo - SP",
    work_model: "Híbrido",
    seniority: "Sênior",
    experience_years_required: "5 anos",
    education_required: "Ciência da Computação",
    responsibilities: ["Projetar APIs REST em FastAPI"],
    requirements: [
      {
        name: "Python e FastAPI",
        category: "competencias_tecnicas",
        importance: "obrigatorio",
        is_eliminatory: false,
        evidence_quote: "- Python e FastAPI",
        evidence_verified: true,
      },
      {
        name: "Kubernetes",
        category: "competencias_tecnicas",
        importance: "desejavel",
        is_eliminatory: false,
        evidence_quote: "- Kubernetes",
        evidence_verified: true,
      },
    ],
    technologies: ["Python", "FastAPI", "Kubernetes"],
    languages: ["Inglês"],
    keywords: ["Python", "FastAPI", "Kubernetes"],
  },
  extraction_method: "deterministic_fallback",
  provider_used: "deterministic",
  provider_fallback_reason: null,
  evidence_report: { total_items_checked: 2, verified_items: 2, unverified_warnings: [] },
  confirmed: false,
};

describe("JobPage (Fase 3)", () => {
  beforeEach(() => {
    document.cookie = "cm_csrf=test_csrf_token; path=/";
  });

  it("parses a pasted job description, displays classified requirements and confirms the job", async () => {
    let current = emptyJob;
    mockFetch((url, init) => {
      if (url.endsWith("/health")) return json(healthy);
      if (url.endsWith("/jobs/current") && (!init?.method || init.method === "GET")) {
        return json(current);
      }
      if (url.endsWith("/jobs/parse")) {
        current = parsedJob;
        return json(current);
      }
      if (url.endsWith("/jobs/current") && init?.method === "PUT") {
        const body = JSON.parse(String(init.body));
        current = { ...parsedJob, data: body.data, confirmed: true };
        return json(current);
      }
      return json(healthy);
    });

    renderRoute("/vaga");
    const textarea = await screen.findByLabelText(/descrição completa da vaga/i);
    await userEvent.click(textarea);
    await userEvent.paste(
      "Engenheiro Backend Sênior na FinPay com experiência em Python, FastAPI, PostgreSQL e Docker.",
    );
    await userEvent.click(screen.getByRole("button", { name: /estruturar requisitos da vaga/i }));

    const titleInput = await screen.findByLabelText(/cargo \*/i);
    expect(titleInput).toHaveValue("Engenheiro Backend Sênior");
    expect(screen.getByDisplayValue("Python e FastAPI")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Kubernetes")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /confirmar requisitos da vaga/i }));
    await waitFor(() => {
      expect(screen.getByText(/vaga confirmada pelo usuário/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: /calcular compatibilidade/i })).toHaveAttribute(
      "href",
      "/compatibilidade",
    );
  });

  it("supports manual entry mode and validates short pasted text", async () => {
    mockFetch((url) => {
      if (url.endsWith("/health")) return json(healthy);
      return json(emptyJob);
    });

    renderRoute("/vaga");
    await userEvent.click(await screen.findByRole("button", { name: /estruturar requisitos da vaga/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/pelo menos 30 caracteres/i);

    await userEvent.click(screen.getByRole("tab", { name: /preenchimento manual/i }));
    expect(await screen.findByLabelText(/cargo \*/i)).toBeInTheDocument();
  });
});

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { json, mockFetch, renderRoute } from "@/test/utils";
import type { ResumeSessionState } from "@/types/resume";

const healthy = {
  status: "ok",
  version: "0.1.0",
  environment: "test",
  ai_provider: "ollama",
  ai_configured: true,
  ai_key_warning: null,
};

const emptyState: ResumeSessionState = {
  has_resume: false,
  filename: null,
  source_kind: null,
  raw_text: "",
  data: null,
  extraction_method: null,
  provider_used: null,
  provider_fallback_reason: null,
  evidence_report: { total_items_checked: 0, verified_items: 0, unverified_warnings: [] },
  confirmed: false,
};

const parsedState: ResumeSessionState = {
  has_resume: true,
  filename: "curriculo.pdf",
  source_kind: "pdf",
  raw_text: "Ana Carolina Mendes\nSão Paulo - SP | ana@email.com\nEngenheira Backend Python e FastAPI.",
  data: {
    personal_info: {
      full_name: "Ana Carolina Mendes",
      email: "ana@email.com",
      phone: "(11) 98765-4321",
      linkedin: "linkedin.com/in/anacarolinamendes",
      location: "São Paulo - SP",
      evidence_quote: "Ana Carolina Mendes | São Paulo - SP | ana@email.com",
    },
    professional_summary: "Engenheira Backend Python e FastAPI.",
    summary_evidence_quote: "Engenheira Backend Python e FastAPI.",
    experiences: [
      {
        role: "Engenheira Backend Sênior",
        company: "TechNova",
        period: "2022 - Atual",
        location: "São Paulo",
        responsibilities: ["Desenvolvimento de APIs REST em FastAPI"],
        achievements: [],
        evidence_quote: "Engenheira Backend Sênior | TechNova | 2022 - Atual",
        evidence_verified: true,
      },
    ],
    education: [
      {
        degree: "Ciência da Computação",
        institution: "USP",
        period: "2015 - 2018",
        evidence_quote: "Ciência da Computação | USP",
        evidence_verified: true,
      },
    ],
    certifications: [],
    technical_skills: [
      {
        name: "FastAPI",
        category: "Técnica",
        evidence_quote: "Engenheira Backend Python e FastAPI.",
        evidence_verified: true,
      },
    ],
    languages: [],
    projects: [],
  },
  extraction_method: "deterministic_fallback",
  provider_used: "deterministic",
  provider_fallback_reason: "Servidor Ollama local indisponível em http://localhost:11434.",
  evidence_report: {
    total_items_checked: 3,
    verified_items: 3,
    unverified_warnings: [],
  },
  confirmed: false,
};

describe("ResumePage (Fase 2)", () => {
  beforeEach(() => {
    document.cookie = "cm_csrf=test_csrf_token; path=/";
  });

  it("rejects unsupported file extensions on the client before calling the API", async () => {
    mockFetch((url) => {
      if (url.endsWith("/health")) return json(healthy);
      return json(emptyState);
    });

    renderRoute("/curriculo");
    const input = await screen.findByLabelText(/selecionar arquivo de currículo/i);
    const badFile = new File(["conteudo"], "virus.exe", { type: "application/octet-stream" });

    await userEvent.upload(input, badFile, { applyAccept: false });
    expect(await screen.findByRole("alert")).toHaveTextContent(/formato não suportado/i);
  });

  it("uploads a valid PDF, parses it, displays evidence quotes and fallback transparency, and confirms edited data", async () => {
    let current = emptyState;
    mockFetch((url, init) => {
      if (url.endsWith("/health")) return json(healthy);
      if (url.endsWith("/resumes/current") && (!init?.method || init.method === "GET")) {
        return json(current);
      }
      if (url.endsWith("/resumes/upload")) {
        return json({
          filename: "curriculo.pdf",
          kind: "pdf",
          size_bytes: 1024,
          char_count: 95,
          raw_text: parsedState.raw_text,
        });
      }
      if (url.endsWith("/resumes/parse")) {
        current = parsedState;
        return json(current);
      }
      if (url.endsWith("/resumes/current") && init?.method === "PUT") {
        const body = JSON.parse(String(init.body));
        current = { ...parsedState, data: body.data, confirmed: true };
        return json(current);
      }
      return json(healthy);
    });

    renderRoute("/curriculo");
    const input = await screen.findByLabelText(/selecionar arquivo de currículo/i);
    const pdfFile = new File(["%PDF-1.4 mock content"], "curriculo.pdf", { type: "application/pdf" });

    await userEvent.upload(input, pdfFile);

    // Form is rendered with extracted values and transparency badge
    const nameInput = await screen.findByLabelText(/nome completo/i);
    expect(nameInput).toHaveValue("Ana Carolina Mendes");
    expect(screen.getByText(/extração determinística local/i)).toBeInTheDocument();
    expect(screen.getByText(/evidências verificadas: 3\/3/i)).toBeInTheDocument();

    // User edits the name and confirms
    await userEvent.clear(nameInput);
    await userEvent.type(nameInput, "Ana Carolina Mendes Editada");

    const confirmBtn = screen.getByRole("button", { name: /confirmar dados do currículo/i });
    await userEvent.click(confirmBtn);

    await waitFor(() => {
      expect(screen.getByText(/dados confirmados pelo usuário/i)).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: /avançar para vaga/i })).toHaveAttribute("href", "/vaga");
  });

  it("allows pasting resume text and shows validation error when text is too short", async () => {
    mockFetch((url) => {
      if (url.endsWith("/health")) return json(healthy);
      return json(emptyState);
    });

    renderRoute("/curriculo");
    await userEvent.click(await screen.findByRole("tab", { name: /colar texto/i }));

    const textarea = screen.getByLabelText(/texto completo do currículo/i);
    await userEvent.type(textarea, "Texto curto");
    await userEvent.click(screen.getByRole("button", { name: /estruturar currículo colado/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/pelo menos 30 caracteres/i);
  });
});

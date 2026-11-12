import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { json, mockFetch, renderRoute } from "@/test/utils";

const healthy = { status: "ok", version: "0.1.0", environment: "test", ai_provider: "gemini", ai_configured: true };

describe("App shell", () => {
  it("renders the hero and the three CTAs", async () => {
    mockFetch(() => json(healthy));
    renderRoute("/");
    expect(screen.getByRole("heading", { level: 1, name: /seu próximo passo profissional começa aqui/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /analisar currículo/i })).toHaveAttribute("href", "/curriculo");
    expect(screen.getByRole("link", { name: /comparar com vaga/i })).toHaveAttribute("href", "/vaga");
    expect(screen.getByRole("link", { name: /criar currículo ats/i })).toHaveAttribute("href", "/curriculo-ats");
    expect(screen.getAllByRole("listitem").length).toBeGreaterThanOrEqual(4);
  });

  it("shows API online status from the health endpoint", async () => {
    mockFetch(() => json(healthy));
    renderRoute("/");
    expect(await screen.findByText(/api online/i)).toBeInTheDocument();
  });

  it("warns when the AI provider is not configured", async () => {
    mockFetch(() => json({ ...healthy, ai_configured: false }));
    renderRoute("/");
    expect(await screen.findByText(/ia não configurada/i)).toBeInTheDocument();
  });

  it("shows an error badge when the API is unreachable", async () => {
    mockFetch(() => json({ error: { code: "x", message: "down" } }, 500));
    renderRoute("/");
    expect(await screen.findByText(/api indisponível/i, {}, { timeout: 4000 })).toBeInTheDocument();
  });

  it("navigates via the CTA to the resume module", async () => {
    mockFetch(() => json(healthy));
    const { router } = renderRoute("/");
    await userEvent.click(screen.getByRole("link", { name: /analisar currículo/i }));
    await waitFor(() => expect(router.state.location.pathname).toBe("/curriculo"));
    expect(screen.getByRole("heading", { level: 1, name: "Currículo" })).toBeInTheDocument();
  });

  it("renders 404 for unknown routes", () => {
    mockFetch(() => json(healthy));
    renderRoute("/nao-existe");
    expect(screen.getByText(/página não encontrada/i)).toBeInTheDocument();
  });
});

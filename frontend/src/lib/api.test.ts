import { api, ApiError } from "@/lib/api";
import { json, mockFetch } from "@/test/utils";

describe("api client", () => {
  beforeEach(() => {
    document.cookie = "cm_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
  });

  it("sends the CSRF header on mutating requests", async () => {
    document.cookie = "cm_csrf=tok123; path=/";
    const spy = mockFetch(() => json({ deleted: true }));
    await api("/sessions/current", { method: "DELETE" });
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("tok123");
    expect(init.credentials).toBe("include");
  });

  it("does not send CSRF header on GET", async () => {
    document.cookie = "cm_csrf=tok123; path=/";
    const spy = mockFetch(() => json({ ok: true }));
    await api("/health");
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(new Headers(init.headers).get("X-CSRF-Token")).toBeNull();
  });

  it("maps error envelopes to ApiError", async () => {
    mockFetch(() => json({ error: { code: "csrf_failed", message: "Sessão inválida" } }, 403));
    await expect(api("/health")).rejects.toMatchObject({ status: 403, code: "csrf_failed", message: "Sessão inválida" });
    await expect(api("/health")).rejects.toBeInstanceOf(ApiError);
  });
});

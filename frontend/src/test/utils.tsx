import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { QueryClient } from "@tanstack/react-query";
import { Providers } from "@/app/providers";
import { routes } from "@/app/routes";

export function renderRoute(path = "/") {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return { router, ...render(<Providers client={client}><RouterProvider router={router} /></Providers>) };
}

/** Explicit test mock for fetch. Never used in production code. */
export function mockFetch(handler: (url: string, init?: RequestInit) => Response | Promise<Response>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((input, init) =>
    Promise.resolve(handler(typeof input === "string" ? input : input.toString(), init)),
  );
}

export const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });

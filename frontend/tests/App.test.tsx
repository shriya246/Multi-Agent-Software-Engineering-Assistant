import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, vi } from "vitest";
import App from "../src/app/App";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "unauthorized", message: "Invalid session" }
        }),
        { status: 401, headers: { "Content-Type": "application/json" } }
      )
    )
  );
});

function renderApp(initialEntries?: string[]) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries ?? ["/"]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

test("renders the home page shell", () => {
  renderApp(["/"]);
  expect(
    screen.getByRole("heading", { name: /codepilot dashboard shell/i })
  ).toBeInTheDocument();
});

test("redirects unauthenticated repository access to login", async () => {
  renderApp(["/repositories"]);
  expect(
    await screen.findByRole("heading", { name: /login/i })
  ).toBeInTheDocument();
});

test("renders registration page", () => {
  renderApp(["/register"]);
  expect(
    screen.getByRole("heading", { name: /create account/i })
  ).toBeInTheDocument();
});

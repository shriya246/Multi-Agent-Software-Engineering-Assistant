import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../src/app/App";

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

test("renders repositories page through routing", () => {
  renderApp(["/repositories"]);
  expect(
    screen.getByRole("heading", { name: /repositories/i })
  ).toBeInTheDocument();
});

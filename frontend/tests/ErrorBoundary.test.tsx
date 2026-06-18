import { render, screen } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { AppErrorBoundary } from "../src/app/ErrorBoundary";

function Exploding(): JSX.Element {
  throw new Error("boom");
}

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders fallback when a child crashes", () => {
  vi.spyOn(console, "error").mockImplementation(() => undefined);
  render(
    <AppErrorBoundary>
      <Exploding />
    </AppErrorBoundary>
  );

  expect(screen.getByText(/something went wrong/i)).toBeInTheDocument();
});

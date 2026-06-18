import type { ErrorInfo, PropsWithChildren, ReactNode } from "react";
import React from "react";

type ErrorBoundaryProps = PropsWithChildren<{
  fallback?: ReactNode;
}>;

type ErrorBoundaryState = {
  hasError: boolean;
};

export class AppErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("app_error_boundary", error, info.componentStack);
  }

  override render(): ReactNode {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="mx-auto max-w-xl rounded-lg border border-slate-800 bg-slate-900 p-6 text-slate-100 shadow-soft">
            <h1 className="text-xl font-semibold">Something went wrong</h1>
            <p className="mt-2 text-sm text-slate-300">
              The interface hit an unexpected error. Please reload the page.
            </p>
          </div>
        )
      );
    }

    return this.props.children;
  }
}

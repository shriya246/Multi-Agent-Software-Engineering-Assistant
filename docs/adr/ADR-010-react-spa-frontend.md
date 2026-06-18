# ADR-010: React SPA Frontend

## Status

Accepted

## Context

CodePilot needs an interactive dashboard for authentication, repositories, streamed job progress, run history, artifacts, Monaco diff views, and approval workflows.

## Decision

Use a React SPA with TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, React Hook Form, Zod, Monaco Editor or Monaco Diff Editor, Vitest, React Testing Library, and Playwright.

## Consequences

- The frontend can support a responsive, workflow-heavy dashboard.
- TanStack Query can handle server state and polling or event-driven refresh.
- Zod can validate client-side request and response assumptions.
- Frontend tests must cover auth flows, repository views, run events, artifact views, and approval actions.

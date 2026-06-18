# System Overview

## Product Overview

CodePilot is a self-hosted Multi-Agent Software Engineering Assistant for public GitHub repositories. It ingests repository source code, extracts syntax-aware structure, builds lexical and semantic indexes, answers questions with citations, investigates bugs, proposes patches, generates tests, executes approved tests in a sandbox, reviews changes, generates documentation, and records auditable run history.

The system is designed for local or trusted single-tenant deployment without paid AI APIs. Ollama is the default local model provider, and provider interfaces allow future alternatives.

## User Journeys

- A user registers, logs in, refreshes a session, views their profile, and logs out.
- A user adds a public GitHub repository and watches ingestion progress.
- A user browses indexed files and symbols.
- A user asks a codebase question and receives an answer with exact file and line citations.
- A user asks for a bug investigation and receives root cause analysis, evidence, and an optional patch.
- A user reviews a generated patch, approves or rejects it, validates it, and optionally applies it.
- A user approves sandbox test execution for a generated patch and reviews logs and artifacts.
- A user requests automated code review or documentation and receives artifacts tied to the run.

## Component Responsibilities

- React frontend: authenticated dashboard, repository management, streamed run progress, artifacts, patch review, and approval workflows.
- FastAPI API: request validation, response shaping, exception mapping, dependency injection, run orchestration, event streaming, and thin HTTP routes.
- Service layer: business rules for repositories, ingestion, retrieval, runs, patches, artifacts, audits, approvals, database health, Redis health, and idempotency reservations.
- Repository classes: database access boundaries for PostgreSQL models.
- Celery workers: long-running ingestion, indexing, agent runs, sandbox execution, artifact creation, and scheduled maintenance jobs.
- PostgreSQL: source of truth for durable application state, migration metadata, repository records, revisions, files, symbols, runs, events, artifacts, patches, test executions, refresh tokens, audit logs, and system metadata.
- Redis: Celery broker, result backend, idempotency reservations, and transient queue data.
- Qdrant: vector index for semantic code retrieval.
- Ollama provider: local chat and embedding inference behind provider interfaces.
- Tree-sitter parser: syntax-aware parsing and symbol extraction.
- Docker sandbox runner: isolated execution for approved tests with no network and strict resource limits.
- Observability stack: metrics, traces, logs, dashboards, and correlation IDs.

## Data Flow

1. The frontend sends authenticated requests to the API.
2. The API validates ownership, records intent, and enqueues long-running work.
3. Workers clone and inspect public GitHub repositories using strict limits.
4. Workers persist repository metadata, files, symbols, events, and artifacts in PostgreSQL.
5. Workers build lexical indexes in PostgreSQL and semantic indexes in Qdrant.
6. Agent workflows retrieve bounded context from PostgreSQL and Qdrant.
7. Ollama returns model output through typed provider interfaces.
8. Structured output is validated before storage.
9. Patches and execution requests wait for explicit human approval.
10. The frontend streams run events and fetches artifacts.

## Background Job Flow

- The API creates an `AgentRun` or ingestion record with an idempotency key where needed.
- The API enqueues a Celery task and returns the durable run identifier.
- Workers emit `AgentRunEvent` records for state transitions and progress.
- Workers store artifacts, patches, validation results, and test execution records.
- Cancellation requests mark runs as canceling and workers stop at safe checkpoints.
- Failed jobs record structured error information without leaking secrets or source contents.

## Agent Workflow

CodePilot uses deterministic LangGraph workflows. Not every request uses every node.

Planned nodes:

- `request_validator`
- `intent_router`
- `repository_context_builder`
- `retriever`
- `code_reader`
- `bug_analyst`
- `patch_generator`
- `test_generator`
- `static_analyzer`
- `sandbox_test_runner`
- `code_reviewer`
- `documentation_generator`
- `approval_gate`
- `finalizer`

Each node receives bounded context, treats repository content as untrusted data, returns typed structured output, records evidence and file references, and logs prompt version, model identifier, duration, status, and error information.

## Storage Boundaries

- PostgreSQL is the durable source of truth.
- Qdrant stores embeddings and vector payload metadata, not authorization truth.
- Redis stores transient queue, result, and idempotency reservation data only.
- Object-like artifacts may initially live in PostgreSQL or a local artifact store, but metadata and ownership live in PostgreSQL.
- Cloned repositories live in controlled worker storage with cleanup policies and must never be treated as durable truth.
- Logs and traces must exclude secrets, JWTs, authorization headers, passwords, and raw source-code contents.

## Trust Boundaries

- Browser to API: authenticated HTTP boundary.
- API to worker queue: internal service boundary.
- Worker to public GitHub: untrusted network input boundary.
- Repository content to parser, retriever, and model prompt: untrusted content boundary.
- Model output to application storage: untrusted generated data boundary.
- Patch to validation and application: untrusted diff boundary.
- Test execution to Docker sandbox: approved but still untrusted execution boundary.
- Internal services to PostgreSQL, Redis, Qdrant, Ollama, and observability services: private network boundary.

## Component Diagram

```mermaid
flowchart LR
    Browser[React SPA] --> API[FastAPI API]
    API --> PG[(PostgreSQL)]
    API --> Redis[(Redis)]
    API --> Worker[Celery Workers]
    Redis --> Worker
    Worker --> PG
    Worker --> Qdrant[(Qdrant)]
    Worker --> Ollama[Ollama Provider]
    Worker --> Parser[Tree-sitter Parser]
    Worker --> GitHub[Public GitHub]
    Worker --> Sandbox[Docker Sandbox]
    API --> OTel[OpenTelemetry Collector]
    Worker --> OTel
    OTel --> Metrics[Prometheus and Tracing]
    Metrics --> Grafana[Grafana]
```

## Repository Ingestion Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant FE as React SPA
    participant API as FastAPI API
    participant PG as PostgreSQL
    participant R as Redis
    participant W as Celery Worker
    participant GH as GitHub
    participant TS as Tree-sitter
    participant Q as Qdrant

    U->>FE: Add public GitHub URL
    FE->>API: POST /api/v1/repositories
    API->>API: Validate HTTPS github.com URL
    API->>PG: Create repository record
    API->>R: Enqueue ingestion job
    API-->>FE: Return repository and run IDs
    W->>R: Claim ingestion job
    W->>GH: Shallow clone with limits
    W->>W: Reject unsafe paths, symlinks, submodules, and oversized files
    W->>TS: Parse supported source files
    W->>PG: Store revisions, files, symbols, and events
    W->>Q: Store embeddings and payload references
    W->>PG: Mark ingestion complete
    FE->>API: Stream run events
    API->>PG: Read events
    API-->>FE: Progress and completion
```

## Bug-Fix Generation Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant FE as React SPA
    participant API as FastAPI API
    participant PG as PostgreSQL
    participant R as Redis
    participant W as Celery Worker
    participant Q as Qdrant
    participant LLM as Ollama

    U->>FE: Request bug investigation
    FE->>API: POST /api/v1/repositories/{repository_id}/bug-fixes
    API->>PG: Verify ownership and create AgentRun
    API->>R: Enqueue agent workflow
    API-->>FE: Return run ID
    W->>PG: Load repository metadata and run request
    W->>Q: Retrieve semantic context
    W->>PG: Retrieve lexical matches and source excerpts
    W->>LLM: Send bounded untrusted context with system rules
    LLM-->>W: Structured bug analysis and patch candidate
    W->>W: Validate structured output and unified diff paths
    W->>PG: Store events, artifacts, and pending patch
    W->>PG: Mark run awaiting approval
    FE->>API: GET /api/v1/runs/{run_id}/events
    API-->>FE: Evidence, artifacts, and patch status
```

## Approved Sandbox Test Execution Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant FE as React SPA
    participant API as FastAPI API
    participant PG as PostgreSQL
    participant R as Redis
    participant W as Celery Worker
    participant S as Docker Sandbox

    U->>FE: Approve test execution for patch
    FE->>API: POST /api/v1/patches/{patch_id}/execute-tests
    API->>PG: Verify ownership, patch approval, and audit request
    API->>R: Enqueue sandbox test job
    API-->>FE: Return test execution ID
    W->>PG: Load patch and repository revision
    W->>W: Validate patch paths and prepare isolated workspace
    W->>S: Run non-root container with no network and limits
    S-->>W: Exit code, bounded logs, and artifacts
    W->>PG: Store TestExecution, logs summary, artifacts, and audit event
    FE->>API: GET /api/v1/runs/{run_id}/events
    API-->>FE: Test status and artifact links
```

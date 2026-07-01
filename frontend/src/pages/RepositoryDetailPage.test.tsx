import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RepositoryDetailPage } from "./RepositoryDetailPage";

const api = vi.hoisted(() => {
  class ApiClientError extends Error {
    status: number;
    payload?: unknown;

    constructor(message: string, status = 500, payload?: unknown) {
      super(message);
      this.name = "ApiClientError";
      this.status = status;
      this.payload = payload;
    }
  }

  return {
    ApiClientError,
    deleteRepository: vi.fn(),
    getRepository: vi.fn(),
    getRepositoryIndexStatus: vi.fn(),
    indexRepository: vi.fn(),
    listRepositoryFiles: vi.fn(),
    listRepositorySymbols: vi.fn(),
    searchRepository: vi.fn(),
    syncRepository: vi.fn()
  };
});

vi.mock("../api/client", () => api);

const repository = {
  id: "repo-1",
  owner_id: "user-1",
  name: "demo",
  normalized_clone_url: "https://github.com/example/demo",
  default_branch: "main",
  status: "ready",
  latest_revision_id: "rev-1",
  indexing_config: {},
  deleted_at: null,
  created_at: "2026-07-01T00:00:00Z",
  updated_at: "2026-07-01T00:00:00Z"
};

const files = [
  {
    id: "file-1",
    revision_id: "rev-1",
    normalized_path: "src/demo.py",
    language: "Python",
    size: 128,
    content_hash: "hash-1",
    line_count: 12,
    indexing_status: "accepted",
    excluded_reason: null
  }
];

const indexStatus = {
  repository_id: "repo-1",
  latest_revision_id: "rev-1",
  latest_indexed_revision_id: "rev-1",
  status: "ready",
  snapshot: {
    id: "snapshot-1",
    revision_id: "rev-1",
    commit_sha: "a".repeat(40),
    status: "ready",
    embedding_model: "deterministic-hash",
    embedding_dimensions: 32,
    statistics: {
      files_seen: 1,
      files_changed: 1,
      chunks_produced: 1,
      reused_vectors: 0,
      parse_successes: 1,
      parse_failures: 0,
      embedding_vectors: 1,
      lexical_terms: 12,
      parser_names: ["Python"],
      failure_reasons: []
    },
    indexed_at: "2026-07-01T00:00:00Z",
    error_code: null,
    error_summary: null
  },
  ready_snapshot_id: "snapshot-1"
};

const symbols = [
  {
    id: "symbol-1",
    file_id: "file-1",
    revision_id: "rev-1",
    normalized_path: "src/demo.py",
    language: "Python",
    symbol_type: "function",
    name: "greet",
    qualified_name: "demo.greet",
    start_line: 1,
    end_line: 5,
    signature: "def greet(name):",
    parent_symbol_id: null,
    symbol_metadata: {}
  }
];

const searchResponse = {
  evidence: [
    {
      path: "src/demo.py",
      language: "Python",
      start_line: 1,
      end_line: 5,
      symbol: "greet",
      score: 0.9876,
      retrieval_method: "hybrid",
      exact_content: "def greet(name):\n    return f\"Hello, {name}\"",
      revision_id: "rev-1",
      commit_sha: "a".repeat(40),
      symbol_type: "function",
      qualified_name: "demo.greet",
      chunk_id: "chunk-1"
    }
  ]
};

describe("RepositoryDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getRepository.mockResolvedValue(repository);
    api.listRepositoryFiles.mockResolvedValue({ files });
    api.getRepositoryIndexStatus.mockResolvedValue(indexStatus);
    api.listRepositorySymbols.mockResolvedValue({ symbols });
    api.indexRepository.mockResolvedValue({
      run_id: "run-1",
      repository_id: "repo-1"
    });
    api.searchRepository.mockResolvedValue(searchResponse);
    api.syncRepository.mockResolvedValue({
      repository,
      run: {
        id: "run-sync",
        owner_id: "user-1",
        repository_id: "repo-1",
        revision_id: null,
        run_type: "repository_sync",
        status: "queued",
        input_summary: "",
        model_provider: "",
        model_identifier: "",
        prompt_version: "",
        started_at: null,
        completed_at: null,
        error_code: null,
        error_message: null,
        input_units: null,
        output_units: null
      }
    });
    api.deleteRepository.mockResolvedValue(repository);
  });

  it("shows index status, symbols, and search results", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/repositories/repo-1"]}>
        <Routes>
          <Route
            path="/repositories/:repositoryId"
            element={<RepositoryDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText("Parse, chunk, and search")).toBeInTheDocument();
    expect(screen.getByText("greet")).toBeInTheDocument();
    expect(screen.getByText("Files seen")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Run indexing" }));
    await waitFor(() => expect(api.indexRepository).toHaveBeenCalledWith("repo-1"));

    await user.type(screen.getByLabelText("Query"), "friendly greeting");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() =>
      expect(api.searchRepository).toHaveBeenCalledWith(
        "repo-1",
        "friendly greeting",
        expect.objectContaining({
          method: "hybrid",
          topK: 5
        })
      )
    );
    expect(await screen.findByText("Score 0.9876")).toBeInTheDocument();
    expect(screen.getByText("demo.greet")).toBeInTheDocument();
  });
});

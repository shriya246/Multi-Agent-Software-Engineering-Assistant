import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ApiClientError,
  deleteRepository,
  getRepository,
  getRepositoryIndexStatus,
  indexRepository,
  listRepositoryFiles,
  listRepositorySymbols,
  searchRepository,
  syncRepository,
  type Repository,
  type RepositoryFile,
  type RepositoryIndexStatus,
  type RepositorySymbol,
  type SearchEvidence
} from "../api/client";
import { StatusBadge } from "./RepositoriesPage";

const pollingStatuses = new Set(["queued", "cloning", "scanning", "deleting"]);
const indexPollingWindowMs = 30_000;

export function RepositoryDetailPage() {
  const { repositoryId } = useParams<{ repositoryId: string }>();
  const navigate = useNavigate();
  const [repository, setRepository] = useState<Repository | null>(null);
  const [files, setFiles] = useState<RepositoryFile[]>([]);
  const [indexStatus, setIndexStatus] = useState<RepositoryIndexStatus | null>(
    null
  );
  const [symbols, setSymbols] = useState<RepositorySymbol[]>([]);
  const [searchResults, setSearchResults] = useState<SearchEvidence[]>([]);
  const [ref, setRef] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchPathPrefix, setSearchPathPrefix] = useState("");
  const [searchLanguage, setSearchLanguage] = useState("");
  const [searchMethod, setSearchMethod] = useState<"dense" | "lexical" | "hybrid">(
    "hybrid"
  );
  const [searchTopK, setSearchTopK] = useState("5");
  const [symbolNameFilter, setSymbolNameFilter] = useState("");
  const [symbolTypeFilter, setSymbolTypeFilter] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncBusy, setSyncBusy] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [indexBusy, setIndexBusy] = useState(false);
  const [searchBusy, setSearchBusy] = useState(false);
  const [indexRequestedAt, setIndexRequestedAt] = useState<number | null>(null);
  const [queuedRunId, setQueuedRunId] = useState<string | null>(null);

  async function refresh() {
    if (!repositoryId) return;
    const [repositoryResponse, fileResponse, indexStatusResponse, symbolResponse] =
      await Promise.all([
        getRepository(repositoryId),
        listRepositoryFiles(repositoryId),
        getRepositoryIndexStatus(repositoryId),
        listRepositorySymbols(repositoryId)
      ]);
    setRepository(repositoryResponse);
    setFiles(fileResponse.files);
    setIndexStatus(indexStatusResponse);
    setSymbols(symbolResponse.symbols);
  }

  useEffect(() => {
    refresh()
      .catch((reason) => {
        setError(
          reason instanceof ApiClientError
            ? reason.message
            : "Unable to load repository"
        );
      })
      .finally(() => setLoading(false));
  }, [repositoryId]);

  useEffect(() => {
    if (!repository || !pollingStatuses.has(repository.status)) return;
    const interval = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(interval);
  }, [repository]);

  useEffect(() => {
    if (!indexRequestedAt) return;
    const refreshInterval = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 3000);
    const timeout = window.setTimeout(() => {
      setIndexRequestedAt(null);
    }, indexPollingWindowMs);
    return () => {
      window.clearInterval(refreshInterval);
      window.clearTimeout(timeout);
    };
  }, [indexRequestedAt]);

  useEffect(() => {
    if (!indexRequestedAt || !repository || !indexStatus) return;
    if (
      indexStatus.latest_indexed_revision_id === repository.latest_revision_id &&
      indexStatus.snapshot?.status === "ready"
    ) {
      setIndexRequestedAt(null);
    }
  }, [indexRequestedAt, indexStatus, repository]);

  async function submitIndex() {
    if (!repositoryId) return;
    setIndexBusy(true);
    setError(null);
    try {
      const response = await indexRepository(repositoryId);
      setQueuedRunId(response.run_id);
      setIndexRequestedAt(Date.now());
      await refresh();
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "Unable to start indexing"
      );
    } finally {
      setIndexBusy(false);
    }
  }

  async function submitSync(event: FormEvent) {
    event.preventDefault();
    if (!repositoryId) return;
    setSyncBusy(true);
    setError(null);
    try {
      await syncRepository(repositoryId, ref);
      setRef("");
      await refresh();
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "Unable to sync repository"
      );
    } finally {
      setSyncBusy(false);
    }
  }

  async function submitSearch(event: FormEvent) {
    event.preventDefault();
    if (!repositoryId || !searchQuery.trim()) return;
    setSearchBusy(true);
    setError(null);
    try {
      const response = await searchRepository(repositoryId, searchQuery.trim(), {
        pathPrefix: searchPathPrefix.trim() || undefined,
        language: searchLanguage.trim() || undefined,
        topK: Number(searchTopK) || 5,
        method: searchMethod
      });
      setSearchResults(response.evidence);
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "Unable to search repository"
      );
    } finally {
      setSearchBusy(false);
    }
  }

  async function confirmDelete() {
    if (!repositoryId) return;
    if (!window.confirm("Delete this repository from CodePilot?")) return;
    setDeleteBusy(true);
    setError(null);
    try {
      await deleteRepository(repositoryId);
      navigate("/repositories");
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "Unable to delete repository"
      );
    } finally {
      setDeleteBusy(false);
    }
  }

  if (loading)
    return <p className="text-sm text-slate-300">Loading repository...</p>;

  if (!repository) {
    return (
      <section className="panel">
        <p className="text-sm text-slate-300">Repository was not found.</p>
        <Link
          className="mt-4 inline-block text-sm text-sky-200"
          to="/repositories"
        >
          Back to repositories
        </Link>
      </section>
    );
  }

  const accepted = files.filter((file) => file.indexing_status === "accepted");
  const excluded = files.length - accepted.length;
  const filteredSymbols = symbols.filter((symbol) => {
    const nameFilter = symbolNameFilter.trim().toLowerCase();
    const typeFilter = symbolTypeFilter.trim().toLowerCase();
    const matchesName =
      !nameFilter ||
      symbol.name.toLowerCase().includes(nameFilter) ||
      symbol.qualified_name.toLowerCase().includes(nameFilter) ||
      symbol.normalized_path.toLowerCase().includes(nameFilter);
    const matchesType =
      !typeFilter || symbol.symbol_type.toLowerCase().includes(typeFilter);
    return matchesName && matchesType;
  });

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <Link className="text-sm text-sky-200" to="/repositories">
            Repositories
          </Link>
          <h1 className="mt-2 text-2xl font-semibold text-slate-50">
            {repository.name}
          </h1>
          <p className="mt-1 break-all text-sm text-slate-400">
            {repository.normalized_clone_url}
          </p>
        </div>
        <StatusBadge status={repository.status} />
      </div>

      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-4">
        <div className="panel">
          <p className="metric-label">Accepted files</p>
          <p className="metric-value">{accepted.length}</p>
        </div>
        <div className="panel">
          <p className="metric-label">Excluded files</p>
          <p className="metric-value">{excluded}</p>
        </div>
        <div className="panel">
          <p className="metric-label">Latest revision</p>
          <p className="truncate text-sm text-slate-300">
            {repository.latest_revision_id ?? "Pending"}
          </p>
        </div>
        <div className="panel">
          <p className="metric-label">Latest indexed revision</p>
          <p className="truncate text-sm text-slate-300">
            {indexStatus?.latest_indexed_revision_id ?? "Not indexed yet"}
          </p>
        </div>
      </div>

      {repository.status === "failed" && (
        <div className="panel border-red-900 bg-red-950/30">
          <p className="text-sm font-medium text-red-100">Ingestion failed</p>
          <p className="mt-1 text-sm text-red-200">
            The repository could not be ingested safely.
          </p>
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
        <div className="space-y-4">
          <section className="panel space-y-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.18em] text-sky-300">
                  Indexing
                </p>
                <h2 className="mt-1 text-lg font-semibold text-slate-50">
                  Parse, chunk, and search
                </h2>
              </div>
              <button
                className="button-primary"
                disabled={indexBusy}
                type="button"
                onClick={() => void submitIndex()}
              >
                {indexBusy ? "Queuing..." : "Run indexing"}
              </button>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <div>
                <p className="metric-label">Snapshot status</p>
                <p className="mt-2 text-sm text-slate-200">
                  {indexStatus?.snapshot?.status ?? "No snapshot yet"}
                </p>
              </div>
              <div>
                <p className="metric-label">Ready snapshot</p>
                <p className="mt-2 break-all text-sm text-slate-200">
                  {indexStatus?.ready_snapshot_id ?? "Not ready"}
                </p>
              </div>
              <div>
                <p className="metric-label">Queued run</p>
                <p className="mt-2 break-all text-sm text-slate-200">
                  {queuedRunId ?? "None"}
                </p>
              </div>
            </div>
            {indexStatus?.snapshot ? (
              <div className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <MetricCard
                    label="Files seen"
                    value={metricValue(indexStatus.snapshot.statistics, "files_seen")}
                  />
                  <MetricCard
                    label="Files changed"
                    value={metricValue(indexStatus.snapshot.statistics, "files_changed")}
                  />
                  <MetricCard
                    label="Chunks"
                    value={metricValue(indexStatus.snapshot.statistics, "chunks_produced")}
                  />
                  <MetricCard
                    label="Reused vectors"
                    value={metricValue(indexStatus.snapshot.statistics, "reused_vectors")}
                  />
                </div>
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <MetricCard
                    label="Parse successes"
                    value={metricValue(indexStatus.snapshot.statistics, "parse_successes")}
                  />
                  <MetricCard
                    label="Parse failures"
                    value={metricValue(indexStatus.snapshot.statistics, "parse_failures")}
                  />
                  <MetricCard
                    label="Embeddings"
                    value={metricValue(indexStatus.snapshot.statistics, "embedding_vectors")}
                  />
                  <MetricCard
                    label="Lexical terms"
                    value={metricValue(indexStatus.snapshot.statistics, "lexical_terms")}
                  />
                </div>
                <div className="flex flex-wrap gap-2">
                  {stringListValue(indexStatus.snapshot.statistics, "parser_names").map(
                    (name) => (
                      <span
                        key={name}
                        className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1 text-xs text-slate-300"
                      >
                        {name}
                      </span>
                    )
                  )}
                </div>
                {stringListValue(indexStatus.snapshot.statistics, "failure_reasons").length >
                0 ? (
                  <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
                    <p className="text-sm font-medium text-slate-100">
                      Parser notes
                    </p>
                    <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">
                      {stringListValue(
                        indexStatus.snapshot.statistics,
                        "failure_reasons"
                      ).map((reason) => (
                        <li key={reason}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ) : (
              <p className="text-sm text-slate-300">
                Run indexing to build symbol and chunk metadata for this repository.
              </p>
            )}
            {indexRequestedAt ? (
              <p className="text-sm text-sky-200">
                Indexing request is being polled for completion.
              </p>
            ) : null}
          </section>

          <section className="panel space-y-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.18em] text-sky-300">
                  Search
                </p>
                <h2 className="mt-1 text-lg font-semibold text-slate-50">
                  Hybrid retrieval over indexed chunks
                </h2>
              </div>
              <span className="text-xs text-slate-400">
                Filters target the current repository revision.
              </span>
            </div>
            <form
              className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr_0.8fr_0.6fr_0.6fr_auto]"
              onSubmit={(event) => void submitSearch(event)}
            >
              <label className="field-label lg:col-span-2">
                Query
                <input
                  className="field-input"
                  placeholder="e.g. friendly greeting or error handling"
                  required
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                />
              </label>
              <label className="field-label">
                Path prefix
                <input
                  className="field-input"
                  placeholder="src/"
                  value={searchPathPrefix}
                  onChange={(event) => setSearchPathPrefix(event.target.value)}
                />
              </label>
              <label className="field-label">
                Language
                <input
                  className="field-input"
                  placeholder="Python"
                  value={searchLanguage}
                  onChange={(event) => setSearchLanguage(event.target.value)}
                />
              </label>
              <label className="field-label">
                Mode
                <select
                  className="field-input"
                  value={searchMethod}
                  onChange={(event) =>
                    setSearchMethod(event.target.value as "dense" | "lexical" | "hybrid")
                  }
                >
                  <option value="hybrid">Hybrid</option>
                  <option value="dense">Dense</option>
                  <option value="lexical">Lexical</option>
                </select>
              </label>
              <label className="field-label">
                Top K
                <input
                  className="field-input"
                  inputMode="numeric"
                  min={1}
                  max={50}
                  type="number"
                  value={searchTopK}
                  onChange={(event) => setSearchTopK(event.target.value)}
                />
              </label>
              <button
                className="button-primary self-end"
                disabled={searchBusy}
                type="submit"
              >
                {searchBusy ? "Searching..." : "Search"}
              </button>
            </form>
            {searchResults.length === 0 ? (
              <p className="text-sm text-slate-300">
                Search results will appear here after you run a query.
              </p>
            ) : (
              <div className="space-y-3">
                {searchResults.map((result, index) => (
                  <article
                    key={`${result.chunk_id}-${index}`}
                    className="rounded-lg border border-slate-800 bg-slate-950 p-4"
                  >
                    <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                      <div>
                        <p className="text-sm font-semibold text-slate-50">
                          {result.path}
                        </p>
                        <p className="mt-1 text-xs uppercase tracking-[0.16em] text-sky-200">
                          {result.symbol_type}{" "}
                          {result.symbol ? `- ${result.symbol}` : ""}
                        </p>
                      </div>
                      <div className="text-right text-xs text-slate-400">
                        <p>Score {result.score.toFixed(4)}</p>
                        <p>{result.retrieval_method}</p>
                      </div>
                    </div>
                    <p className="mt-3 text-sm text-slate-300">
                      Lines {result.start_line} to {result.end_line}
                    </p>
                    {result.qualified_name ? (
                      <p className="mt-1 text-xs text-slate-400">
                        {result.qualified_name}
                      </p>
                    ) : null}
                    <pre className="mt-3 overflow-auto rounded-md border border-slate-800 bg-slate-900 p-3 text-xs leading-6 text-slate-200">
                      {result.exact_content}
                    </pre>
                  </article>
                ))}
              </div>
            )}
          </section>
        </div>

        <div className="space-y-4">
          <section className="panel space-y-4">
            <div>
              <p className="text-sm uppercase tracking-[0.18em] text-sky-300">
                Symbols
              </p>
              <h2 className="mt-1 text-lg font-semibold text-slate-50">
                Repository symbol browser
              </h2>
            </div>
            <div className="grid gap-3">
              <label className="field-label">
                Name filter
                <input
                  className="field-input"
                  placeholder="greet"
                  value={symbolNameFilter}
                  onChange={(event) => setSymbolNameFilter(event.target.value)}
                />
              </label>
              <label className="field-label">
                Kind filter
                <input
                  className="field-input"
                  placeholder="function"
                  value={symbolTypeFilter}
                  onChange={(event) => setSymbolTypeFilter(event.target.value)}
                />
              </label>
            </div>
            {filteredSymbols.length === 0 ? (
              <p className="text-sm text-slate-300">
                No symbols match the current filters.
              </p>
            ) : (
              <ul className="space-y-3">
                {filteredSymbols.slice(0, 50).map((symbol) => (
                  <li
                    key={symbol.id}
                    className="rounded-lg border border-slate-800 bg-slate-950 p-4"
                  >
                    <p className="text-sm font-semibold text-slate-50">
                      {symbol.name}
                    </p>
                    <p className="mt-1 text-xs uppercase tracking-[0.16em] text-sky-200">
                      {symbol.symbol_type}
                    </p>
                    <p className="mt-2 break-all text-xs text-slate-400">
                      {symbol.normalized_path}
                    </p>
                    <p className="mt-2 text-sm text-slate-300">
                      Lines {symbol.start_line} to {symbol.end_line}
                    </p>
                    {symbol.signature ? (
                      <p className="mt-2 overflow-hidden text-ellipsis whitespace-nowrap rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-xs text-slate-200">
                        {symbol.signature}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel overflow-hidden p-0">
            <div className="border-b border-slate-800 p-5">
              <h2 className="text-base font-semibold text-slate-50">
                File summary
              </h2>
            </div>
            {files.length === 0 ? (
              <p className="p-5 text-sm text-slate-300">
                No file metadata has been recorded yet.
              </p>
            ) : (
              <ul className="max-h-[520px] divide-y divide-slate-800 overflow-auto">
                {files.slice(0, 250).map((file) => (
                  <li
                    key={file.id}
                    className="grid gap-2 p-4 md:grid-cols-[1fr_120px_120px]"
                  >
                    <span className="break-all text-sm text-slate-100">
                      {file.normalized_path}
                    </span>
                    <span className="text-sm text-slate-400">
                      {file.language ?? "Unknown"}
                    </span>
                    <span className="text-sm text-slate-400">
                      {file.excluded_reason ?? `${file.line_count} lines`}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>

      <form
        className="panel grid gap-4 md:grid-cols-[1fr_auto_auto]"
        onSubmit={(event) => void submitSync(event)}
      >
        <label className="field-label">
          Sync ref
          <input
            className="field-input"
            placeholder="main, tag, or commit"
            value={ref}
            onChange={(event) => setRef(event.target.value)}
          />
        </label>
        <button
          className="button-primary self-end"
          disabled={syncBusy}
          type="submit"
        >
          Sync
        </button>
        <button
          className="button-secondary self-end"
          disabled={deleteBusy}
          type="button"
          onClick={() => void confirmDelete()}
        >
          Delete
        </button>
      </form>
    </section>
  );
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950 p-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-50">{value}</p>
    </div>
  );
}

function metricValue(stats: Record<string, unknown>, key: string): number {
  const value = stats[key];
  return typeof value === "number" ? value : 0;
}

function stringListValue(stats: Record<string, unknown>, key: string): string[] {
  const value = stats[key];
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

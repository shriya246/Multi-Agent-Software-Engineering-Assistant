import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ApiClientError,
  deleteRepository,
  getRepository,
  listRepositoryFiles,
  syncRepository,
  type Repository,
  type RepositoryFile
} from "../api/client";
import { StatusBadge } from "./RepositoriesPage";

const pollingStatuses = new Set(["queued", "cloning", "scanning", "deleting"]);

export function RepositoryDetailPage() {
  const { repositoryId } = useParams<{ repositoryId: string }>();
  const navigate = useNavigate();
  const [repository, setRepository] = useState<Repository | null>(null);
  const [files, setFiles] = useState<RepositoryFile[]>([]);
  const [ref, setRef] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    if (!repositoryId) return;
    const [repositoryResponse, fileResponse] = await Promise.all([
      getRepository(repositoryId),
      listRepositoryFiles(repositoryId)
    ]);
    setRepository(repositoryResponse);
    setFiles(fileResponse.files);
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

  async function submitSync(event: FormEvent) {
    event.preventDefault();
    if (!repositoryId) return;
    setBusy(true);
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
      setBusy(false);
    }
  }

  async function confirmDelete() {
    if (!repositoryId) return;
    if (!window.confirm("Delete this repository from CodePilot?")) return;
    setBusy(true);
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
      setBusy(false);
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

      <div className="grid gap-4 md:grid-cols-3">
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
      </div>

      {repository.status === "failed" && (
        <div className="panel border-red-900 bg-red-950/30">
          <p className="text-sm font-medium text-red-100">Ingestion failed</p>
          <p className="mt-1 text-sm text-red-200">
            The repository could not be ingested safely.
          </p>
        </div>
      )}

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
          disabled={busy}
          type="submit"
        >
          Sync
        </button>
        <button
          className="button-secondary self-end"
          disabled={busy}
          type="button"
          onClick={() => void confirmDelete()}
        >
          Delete
        </button>
      </form>

      <div className="panel overflow-hidden p-0">
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
      </div>
    </section>
  );
}

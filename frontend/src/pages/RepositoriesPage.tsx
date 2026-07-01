import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ApiClientError,
  createRepository,
  listRepositories,
  type Repository
} from "../api/client";

const activeStatuses = new Set(["queued", "cloning", "scanning", "deleting"]);

export function RepositoriesPage() {
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [cloneUrl, setCloneUrl] = useState("");
  const [ref, setRef] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  async function refresh() {
    const response = await listRepositories();
    setRepositories(response.repositories);
  }

  useEffect(() => {
    let alive = true;
    listRepositories()
      .then((response) => {
        if (alive) setRepositories(response.repositories);
      })
      .catch((reason) => {
        if (alive) {
          setError(
            reason instanceof ApiClientError
              ? reason.message
              : "Unable to load repositories"
          );
        }
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    if (
      !repositories.some((repository) => activeStatuses.has(repository.status))
    )
      return;
    const interval = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(interval);
  }, [repositories]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await createRepository(cloneUrl, ref);
      setCloneUrl("");
      setRef("");
      await refresh();
    } catch (reason) {
      setError(
        reason instanceof ApiClientError
          ? reason.message
          : "Unable to add repository"
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="space-y-6">
      <div>
        <p className="text-sm uppercase tracking-[0.18em] text-sky-300">
          Repositories
        </p>
        <h1 className="mt-2 text-2xl font-semibold text-slate-50">
          Secure ingestion
        </h1>
      </div>

      <form
        className="panel grid gap-4 md:grid-cols-[1fr_180px_auto]"
        onSubmit={(event) => void submit(event)}
      >
        <label className="field-label">
          GitHub HTTPS URL
          <input
            className="field-input"
            placeholder="https://github.com/owner/repository"
            required
            value={cloneUrl}
            onChange={(event) => setCloneUrl(event.target.value)}
          />
        </label>
        <label className="field-label">
          Ref
          <input
            className="field-input"
            placeholder="main"
            value={ref}
            onChange={(event) => setRef(event.target.value)}
          />
        </label>
        <button
          className="button-primary self-end"
          disabled={submitting}
          type="submit"
        >
          {submitting ? "Queuing..." : "Add"}
        </button>
      </form>

      {error && (
        <p className="error-message" role="alert">
          {error}
        </p>
      )}

      <div className="panel overflow-hidden p-0">
        {loading ? (
          <p className="p-5 text-sm text-slate-300">Loading repositories...</p>
        ) : repositories.length === 0 ? (
          <p className="p-5 text-sm text-slate-300">
            No repositories have been added yet.
          </p>
        ) : (
          <ul className="divide-y divide-slate-800">
            {repositories.map((repository) => (
              <li
                key={repository.id}
                className="grid gap-3 p-5 md:grid-cols-[1fr_auto]"
              >
                <div>
                  <Link
                    className="text-base font-semibold text-slate-50 hover:text-sky-200"
                    to={`/repositories/${repository.id}`}
                  >
                    {repository.name}
                  </Link>
                  <p className="mt-1 break-all text-sm text-slate-400">
                    {repository.normalized_clone_url}
                  </p>
                </div>
                <StatusBadge status={repository.status} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "failed"
      ? "status-bad"
      : activeStatuses.has(status)
        ? "status-warn"
        : "status-good";
  return (
    <span className={`status-badge ${tone}`}>
      {status.replaceAll("_", " ")}
    </span>
  );
}

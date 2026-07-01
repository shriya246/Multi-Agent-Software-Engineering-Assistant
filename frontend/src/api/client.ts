export type ApiErrorPayload = {
  code: string;
  message: string;
  correlation_id: string;
  details?: unknown;
};

export type ApiErrorResponse = {
  error: ApiErrorPayload;
};

export class ApiClientError extends Error {
  readonly status: number;
  readonly payload?: ApiErrorResponse;

  constructor(message: string, status: number, payload?: ApiErrorResponse) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.payload = payload;
  }
}

let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getCookie(name: string): string | null {
  const prefix = `${encodeURIComponent(name)}=`;
  const item = document.cookie
    .split("; ")
    .find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : null;
}

export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL?.trim() || "/api/v1";
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...(init?.headers ?? {})
    },
    ...init
  });

  if (!response.ok) {
    let payload: ApiErrorResponse | undefined;
    try {
      payload = (await response.json()) as ApiErrorResponse;
    } catch {
      payload = undefined;
    }
    throw new ApiClientError(
      payload?.error.message ?? response.statusText,
      response.status,
      payload
    );
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export type Repository = {
  id: string;
  owner_id: string;
  name: string;
  normalized_clone_url: string;
  default_branch: string | null;
  status: string;
  latest_revision_id: string | null;
  indexing_config: Record<string, unknown>;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
};

export type RepositoryFile = {
  id: string;
  revision_id: string;
  normalized_path: string;
  language: string | null;
  size: number;
  content_hash: string;
  line_count: number;
  indexing_status: string;
  excluded_reason: string | null;
};

export type AgentRun = {
  id: string;
  owner_id: string;
  repository_id: string;
  revision_id: string | null;
  run_type: string;
  status: string;
  input_summary: string;
  model_provider: string;
  model_identifier: string;
  prompt_version: string;
  started_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  error_message: string | null;
  input_units: number | null;
  output_units: number | null;
};

export type AgentRunEvent = {
  id: string;
  run_id: string;
  sequence: number;
  event_type: string;
  public_message: string;
  created_at: string;
};

export function listRepositories() {
  return apiRequest<{ repositories: Repository[] }>("/repositories");
}

export function createRepository(cloneUrl: string, ref?: string) {
  return apiRequest<{ repository: Repository; run: AgentRun | null }>(
    "/repositories",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clone_url: cloneUrl, ref: ref?.trim() || null })
    }
  );
}

export function getRepository(repositoryId: string) {
  return apiRequest<Repository>(`/repositories/${repositoryId}`);
}

export function syncRepository(repositoryId: string, ref?: string) {
  return apiRequest<{ repository: Repository; run: AgentRun }>(
    `/repositories/${repositoryId}/sync`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ref: ref?.trim() || null })
    }
  );
}

export function deleteRepository(repositoryId: string) {
  return apiRequest<Repository>(`/repositories/${repositoryId}`, {
    method: "DELETE"
  });
}

export function listRepositoryFiles(repositoryId: string) {
  return apiRequest<{ files: RepositoryFile[] }>(
    `/repositories/${repositoryId}/files`
  );
}

export function getRun(runId: string) {
  return apiRequest<AgentRun>(`/runs/${runId}`);
}

export function listRunEvents(runId: string) {
  return apiRequest<{ events: AgentRunEvent[] }>(`/runs/${runId}/events`);
}

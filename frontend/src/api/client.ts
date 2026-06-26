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
  const item = document.cookie.split("; ").find((value) => value.startsWith(prefix));
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

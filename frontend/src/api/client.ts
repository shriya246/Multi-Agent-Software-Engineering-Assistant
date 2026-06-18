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

export function getApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL?.trim() || "/api/v1";
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit
): Promise<T> {
  const response = await fetch(`${getApiBaseUrl()}${path}`, {
    headers: {
      Accept: "application/json",
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

  return (await response.json()) as T;
}

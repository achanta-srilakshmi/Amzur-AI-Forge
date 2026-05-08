/**
 * Central API client.
 * All fetch calls in the application must go through this module.
 * Never call fetch or axios directly in components or hooks.
 *
 * The Vite dev-server proxy forwards /api/* to http://localhost:8000.
 * In production the same relative path is used — no base URL needed.
 */

const BASE = "/api";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

async function request<T>(
  method: HttpMethod,
  path: string,
  body?: unknown
): Promise<T> {
  const isFormData = body instanceof FormData;
  
  const response = await fetch(`${BASE}${path}`, {
    method,
    credentials: "include", // send httpOnly cookie with every request
    headers: isFormData ? undefined : (body ? { "Content-Type": "application/json" } : undefined),
    body: isFormData ? body : (body ? JSON.stringify(body) : undefined),
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new ApiError(response.status, detail);
  }

  // 204 No Content — nothing to parse
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;

  constructor(status: number, detail: unknown) {
    super(`API error ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

/** Upload a file as multipart/form-data (bypasses the JSON helper above). */
export async function uploadFile(
  path: string,
  formData: FormData
): Promise<unknown> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });

  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new ApiError(response.status, detail);
  }

  return response.json();
}

export async function uploadAttachments<T>(
  threadId: string,
  files: File[]
): Promise<T> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  return uploadFile(`/threads/${threadId}/attachments`, formData) as Promise<T>;
}

/** Upload a PDF document for RAG ingestion. */
export async function uploadDocument<T>(
  threadId: string,
  file: File
): Promise<T> {
  const formData = new FormData();
  formData.append("file", file);
  return uploadFile(`/threads/${threadId}/documents`, formData) as Promise<T>;
}

export async function getThreadDocuments<T>(threadId: string): Promise<T> {
  return api.get<T>(`/threads/${threadId}/documents`);
}

/** Open a streaming SSE connection and yield text chunks. */
export async function* streamResponse(
  path: string,
  body: unknown
): AsyncGenerator<string> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok || !response.body) {
    const detail = await response.json().catch(() => ({}));
    throw new ApiError(response.status, detail);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    yield decoder.decode(value, { stream: true });
  }
}

/** Open a streaming SSE connection using multipart/form-data payload. */
export async function* streamMultipartResponse(
  path: string,
  formData: FormData,
  signal?: AbortSignal
): AsyncGenerator<string> {
  const response = await fetch(`${BASE}${path}`, {
    method: "POST",
    credentials: "include",
    body: formData,
    signal,
  });

  if (!response.ok || !response.body) {
    const detail = await response.json().catch(() => ({}));
    throw new ApiError(response.status, detail);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    yield decoder.decode(value, { stream: true });
  }
}

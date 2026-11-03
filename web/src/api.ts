/** 统一 HTTP 客户端：带 Cookie、写操作带 CSRF、401 交给外层跳登录。 */

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;

  constructor(status: number, message: string, code = "error", details: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export class ConflictError extends ApiError {
  constructor(status: number, message: string, code = "conflict", details: unknown = null) {
    super(status, message, code, details);
    this.name = "ConflictError";
  }
}

let unauthorizedHandler: (() => void) | null = null;

export function setUnauthorizedHandler(handler: () => void): void {
  unauthorizedHandler = handler;
}

function readCookie(name: string): string | null {
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const item = part.trim();
    if (item.startsWith(prefix)) {
      return decodeURIComponent(item.slice(prefix.length));
    }
  }
  return null;
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options.headers ?? {}),
  };
  if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = readCookie("panel_csrf");
    if (token) {
      headers["X-CSRF-Token"] = token;
    }
  }

  const response = await fetch(path, {
    method,
    headers,
    credentials: "same-origin",
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  let payload: Record<string, unknown> = {};
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text) as Record<string, unknown>;
    } catch {
      payload = { message: text };
    }
  }

  if (response.ok) {
    return payload as T;
  }

  const message = typeof payload.message === "string" ? payload.message : `请求失败（${response.status}）`;
  const code = typeof payload.code === "string" ? payload.code : "error";
  const details = payload.details ?? null;

  if (response.status === 401) {
    unauthorizedHandler?.();
  }
  if (response.status === 409) {
    throw new ConflictError(response.status, message, code, details);
  }
  throw new ApiError(response.status, message, code, details);
}

export function get<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function post<T>(path: string, body?: unknown, headers?: Record<string, string>): Promise<T> {
  return request<T>(path, { method: "POST", body, headers });
}

export function put<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, { method: "PUT", body });
}

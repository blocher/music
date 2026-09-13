const getCookie = (name: string) =>
  document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(`${name}=`))
    ?.split("=")
    .slice(1)
    .join("=") ?? "";

export class ApiError extends Error {
  status: number;
  payload: unknown;

  constructor(status: number, payload: unknown) {
    super(typeof payload === "object" && payload && "detail" in payload ? String(payload.detail) : `Request failed (${status})`);
    this.status = status;
    this.payload = payload;
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const csrf = getCookie("csrftoken");
  if (csrf) headers.set("X-CSRFToken", decodeURIComponent(csrf));
  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  if (response.status === 204) return undefined as T;
  const payload = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, payload);
  return payload as T;
}

export const post = <T>(path: string, body: unknown) => api<T>(path, { method: "POST", body: JSON.stringify(body) });
export const patch = <T>(path: string, body: unknown) => api<T>(path, { method: "PATCH", body: JSON.stringify(body) });

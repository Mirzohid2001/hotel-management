/** Default API base — change for device/emulator. */
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000/api/v1";

export type ApiOk<T> = { ok: true; data: T };
export type ApiErr = { ok: false; error: string };

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  token?: string | null;
  tenantId?: number | null;
  hotelId?: number | null;
};

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }
  if (options.tenantId) {
    headers["X-Tenant-Id"] = String(options.tenantId);
  }
  if (options.hotelId) {
    headers["X-Hotel-Id"] = String(options.hotelId);
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method || "GET",
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });

  let json: ApiOk<T> | ApiErr;
  try {
    json = await res.json();
  } catch {
    throw new ApiError(`Bad response (${res.status})`, res.status);
  }

  if (!res.ok || !json.ok) {
    const msg = "error" in json ? json.error : `HTTP ${res.status}`;
    throw new ApiError(msg, res.status);
  }
  return json.data;
}

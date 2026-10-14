// Cookie-authenticated fetch and the API's `detail` error text. auth.ts and
// social.ts each kept a private copy of both.

export function req(path: string, init?: RequestInit): Promise<Response> {
  return fetch(path, { credentials: "include", ...init });
}

// FastAPI sends `detail` as a string, or as a validation list of `{msg}`.
export function messageFromDetail(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object" || !("detail" in data)) return fallback;
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msg = (detail[0] as { msg?: unknown } | undefined)?.msg;
    if (typeof msg === "string" && msg) return msg;
  }
  return fallback;
}

// Expected failures on some endpoints come back as 200 {"error": "..."} so the
// browser doesn't log a 4xx (see _SOFT_FAIL_PATHS in the API). Returns that
// message, or null when the body isn't such an error.
export function softError(data: unknown): string | null {
  if (!data || typeof data !== "object" || !("error" in data)) return null;
  const msg = (data as { error?: unknown }).error;
  return typeof msg === "string" && msg ? msg : "Something went wrong. Try again.";
}

export async function messageFromResponse(res: Response, fallback: string): Promise<string> {
  try {
    return messageFromDetail(await res.json(), fallback);
  } catch {
    return fallback;
  }
}

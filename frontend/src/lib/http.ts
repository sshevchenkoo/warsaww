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

export async function messageFromResponse(res: Response, fallback: string): Promise<string> {
  try {
    return messageFromDetail(await res.json(), fallback);
  } catch {
    return fallback;
  }
}

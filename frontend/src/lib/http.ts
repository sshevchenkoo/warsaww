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

// Multipart POST with upload progress. XMLHttpRequest, not fetch: fetch has no
// upload-progress event. onProgress gets 0–100 while the bytes go up. Resolves
// with the JSON body of a 2xx; otherwise throws with the API's `detail`.
export function uploadWithProgress(
  path: string,
  form: FormData,
  onProgress: ((percent: number) => void) | undefined,
  fallback: string,
): Promise<unknown> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", path);
    xhr.withCredentials = true;
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response);
        return;
      }
      // null when the error body isn't JSON
      reject(new Error(messageFromDetail(xhr.response, fallback)));
    };
    xhr.onerror = () => reject(new Error("Upload failed. Check your connection."));
    xhr.send(form);
  });
}

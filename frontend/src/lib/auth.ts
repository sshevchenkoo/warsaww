// Client for the auth + saved-items endpoints. All calls go to relative paths
// (proxied to the API in dev, same-origin in prod) and send the session cookie.

import type { Card } from "./api";
import { messageFromDetail, messageFromResponse, req } from "./http";

export type User = {
  id: string;
  email: string | null;
  name: string | null;
  avatar_url: string | null;
  email_verified: boolean;
  // Requested new email (PATCH /me) not yet confirmed by code; `email` keeps
  // working for login until then.
  pending_email: string | null;
  // Only password accounts can change their email (Google manages the rest).
  has_password: boolean;
  // Password logins mail a code when this is on. Google accounts stay false;
  // their second factor is the Google account itself.
  two_factor_enabled: boolean;
};

// Password login either opens a session or, when two-factor is on, parks it
// until POST /auth/login/2fa. That response has no user fields.
export type LoginResult = User | { pending_2fa: true };

export const LOGIN_URL = "/auth/login/google";

export async function getMe(): Promise<User | null> {
  const res = await req("/me");
  return res.ok ? res.json() : null;
}

// Send JSON (POST by default); on failure throw with the API's error message.
async function authJson(path: string, body: object, method = "POST"): Promise<unknown> {
  const res = await req(path, {
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(await messageFromResponse(res, "Something went wrong. Try again."));
  }
  return res.json();
}

function asUser(data: unknown): User {
  return data as User;
}

export function register(email: string, password: string, name?: string): Promise<User> {
  return authJson("/auth/register", { email, password, name: name || null }).then(asUser);
}

export async function login(email: string, password: string): Promise<LoginResult> {
  const data = await authJson("/auth/login", { email, password });
  if (
    typeof data === "object" &&
    data !== null &&
    "pending_2fa" in data &&
    (data as { pending_2fa?: unknown }).pending_2fa === true &&
    !("id" in data)
  ) {
    return { pending_2fa: true };
  }
  return asUser(data);
}

// Finish a password login that came back as pending_2fa. The code was emailed
// by POST /auth/login; a wrong or expired one throws the API's message.
export function login2fa(code: string): Promise<User> {
  return authJson("/auth/login/2fa", { code }).then(asUser);
}

// Confirm the email with the 6-digit code we mailed; returns the updated user
// (email_verified flips to true). Throws with the API's message on a bad/expired
// code or too many attempts.
export function verifyEmail(code: string): Promise<User> {
  return authJson("/auth/verify", { code }).then(asUser);
}

// Edit the profile. Omitted fields stay unchanged; `name: null` clears it. A new
// `email` needs `current_password` and only lands in `pending_email` until the
// mailed code confirms it; sending the current email cancels a pending change.
export function updateMe(patch: {
  name?: string | null;
  email?: string;
  current_password?: string;
  two_factor_enabled?: boolean;
}): Promise<User> {
  return authJson("/me", patch, "PATCH").then(asUser);
}

// Ask the API to email a fresh verification code to the logged-in user.
export async function resendVerification(): Promise<void> {
  await req("/auth/resend", { method: "POST" });
}

export async function getSavedIds(): Promise<string[]> {
  const res = await req("/me/saved/ids");
  return res.ok ? res.json() : [];
}

export async function getSaved(signal?: AbortSignal): Promise<Card[]> {
  const res = await req("/me/saved", { signal });
  return res.ok ? res.json() : [];
}

// POST/DELETE /me/saved. Throws the API message (or a connection fallback) so
// the heart can revert when the call fails. A 2xx body is {status}.
async function savedMutation(id: string, method: "POST" | "DELETE"): Promise<void> {
  let res: Response;
  try {
    res = await req(`/me/saved/${id}`, { method });
  } catch {
    throw new Error("Couldn't update saved items. Check your connection.");
  }
  if (res.ok) return;
  throw new Error(await messageFromResponse(res, "Couldn't update saved items."));
}

export function saveItem(id: string): Promise<void> {
  return savedMutation(id, "POST");
}

export function unsaveItem(id: string): Promise<void> {
  return savedMutation(id, "DELETE");
}

export function logout() {
  return req("/auth/logout", { method: "POST" });
}

// GET /me/export returns a JSON file (profile, saved items, friendships, shares).
// Trigger a download of that body. The avatar image itself is not in the file.
export async function downloadMyData(): Promise<void> {
  const res = await req("/me/export");
  if (!res.ok) throw new Error(await messageFromResponse(res, "Couldn't download your data. Try again."));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const match = res.headers.get("Content-Disposition")?.match(/filename="([^"]+)"/);
  a.download = match?.[1] || "warsaw-events-data.json";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// DELETE /me. Password accounts must send the current password; Google accounts
// have none, so the body stays empty. The API clears the session and emails a
// notice that the account was deleted.
export async function deleteAccount(currentPassword?: string): Promise<void> {
  const res = await req("/me", {
    method: "DELETE",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(currentPassword ? { current_password: currentPassword } : {}),
  });
  if (!res.ok) throw new Error(await messageFromResponse(res, "Couldn't delete the account. Try again."));
}

// Upload a new avatar (multipart). Returns the new cache-busted avatar_url, or
// throws with the API's error message (e.g. too large / not an image).
// XMLHttpRequest, not fetch: fetch has no upload-progress event. onProgress
// gets 0–100 while the bytes go up; the server then still re-encodes the image.
export function uploadAvatar(file: File, onProgress?: (percent: number) => void): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/me/avatar");
    xhr.withCredentials = true;
    xhr.responseType = "json";
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300 && xhr.response?.avatar_url) {
        resolve(xhr.response.avatar_url as string);
        return;
      }
      // null when the error body isn't JSON
      reject(new Error(messageFromDetail(xhr.response, "Upload failed. Try a smaller image.")));
    };
    xhr.onerror = () => reject(new Error("Upload failed. Check your connection."));
    xhr.send(form);
  });
}

// Remove the uploaded avatar (the UI falls back to the initial placeholder).
export async function deleteAvatar(): Promise<void> {
  const res = await req("/me/avatar", { method: "DELETE" });
  if (!res.ok) throw new Error("Couldn't remove the photo. Try again.");
}

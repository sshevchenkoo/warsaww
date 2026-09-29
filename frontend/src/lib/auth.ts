// Client for the auth + saved-items endpoints. All calls go to relative paths
// (proxied to the API in dev, same-origin in prod) and send the session cookie.

import type { Card } from "./api";

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
};

export const LOGIN_URL = "/auth/login/google";

function req(path: string, init?: RequestInit) {
  return fetch(path, { credentials: "include", ...init });
}

export async function getMe(): Promise<User | null> {
  const res = await req("/me");
  return res.ok ? res.json() : null;
}

// Send JSON (POST by default); on failure throw with the API's error message.
async function authPost(path: string, body: object, method = "POST"): Promise<User> {
  const res = await req(path, {
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    let msg = "Something went wrong. Try again.";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") msg = data.detail;
      else if (Array.isArray(data.detail) && data.detail[0]?.msg) msg = data.detail[0].msg;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(msg);
  }
  return res.json();
}

export function register(email: string, password: string, name?: string): Promise<User> {
  return authPost("/auth/register", { email, password, name: name || null });
}

export function login(email: string, password: string): Promise<User> {
  return authPost("/auth/login", { email, password });
}

// Confirm the email with the 6-digit code we mailed; returns the updated user
// (email_verified flips to true). Throws with the API's message on a bad/expired
// code or too many attempts.
export function verifyEmail(code: string): Promise<User> {
  return authPost("/auth/verify", { code });
}

// Edit the profile. Omitted fields stay unchanged; `name: null` clears it. A new
// `email` needs `current_password` and only lands in `pending_email` until the
// mailed code confirms it; sending the current email cancels a pending change.
export function updateMe(patch: {
  name?: string | null;
  email?: string;
  current_password?: string;
}): Promise<User> {
  return authPost("/me", patch, "PATCH");
}

// Ask the API to email a fresh verification code to the logged-in user.
export async function resendVerification(): Promise<void> {
  await req("/auth/resend", { method: "POST" });
}

export async function getSavedIds(): Promise<string[]> {
  const res = await req("/me/saved/ids");
  return res.ok ? res.json() : [];
}

export async function getSaved(): Promise<Card[]> {
  const res = await req("/me/saved");
  return res.ok ? res.json() : [];
}

export function saveItem(id: string) {
  return req(`/me/saved/${id}`, { method: "POST" });
}

export function unsaveItem(id: string) {
  return req(`/me/saved/${id}`, { method: "DELETE" });
}

export function logout() {
  return req("/auth/logout", { method: "POST" });
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
      const detail = xhr.response?.detail; // null when the error body isn't JSON
      reject(new Error(typeof detail === "string" ? detail : "Upload failed. Try a smaller image."));
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

// Client for the auth + saved-items endpoints. All calls go to relative paths
// (proxied to the API in dev, same-origin in prod) and send the session cookie.

import type { Card } from "./api";

export type User = {
  id: string;
  email: string | null;
  name: string | null;
  avatar_url: string | null;
  email_verified: boolean;
};

export const LOGIN_URL = "/auth/login/google";

function req(path: string, init?: RequestInit) {
  return fetch(path, { credentials: "include", ...init });
}

export async function getMe(): Promise<User | null> {
  const res = await req("/me");
  return res.ok ? res.json() : null;
}

// POST credentials; on failure throw with the API's error message.
async function authPost(path: string, body: object): Promise<User> {
  const res = await req(path, {
    method: "POST",
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
export async function uploadAvatar(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const res = await req("/me/avatar", { method: "POST", body: form });
  if (!res.ok) {
    let msg = "Upload failed. Try a smaller image.";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") msg = data.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(msg);
  }
  return (await res.json()).avatar_url as string;
}

export function deleteAvatar() {
  return req("/me/avatar", { method: "DELETE" });
}

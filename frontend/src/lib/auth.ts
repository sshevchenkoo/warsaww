// Client for the auth + saved-items endpoints. All calls go to relative paths
// (proxied to the API in dev, same-origin in prod) and send the session cookie.

import type { Card } from "./api";

export type User = {
  id: string;
  email: string | null;
  name: string | null;
  avatar_url: string | null;
};

export const LOGIN_URL = "/auth/login/google";

function req(path: string, init?: RequestInit) {
  return fetch(path, { credentials: "include", ...init });
}

export async function getMe(): Promise<User | null> {
  const res = await req("/me");
  return res.ok ? res.json() : null;
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

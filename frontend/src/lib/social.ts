// Client for the social endpoints: user search, friends (request → accept),
// and sharing events with friends. Relative paths + session cookie, like auth.ts.

import type { Card } from "./api";

export type Friendship =
  | "self"
  | "friends"
  | "request_sent"
  | "request_received"
  | "none";

export type PublicUser = {
  id: string;
  name: string | null;
  avatar_url: string | null;
  friendship: Friendship;
};

export type SharedEvent = {
  id: string;
  item: Card;
  from_user: PublicUser;
  message: string | null;
  created_at: string;
};

function req(path: string, init?: RequestInit) {
  return fetch(path, { credentials: "include", ...init });
}

async function asJson<T>(res: Response, fallback: T): Promise<T> {
  return res.ok ? res.json() : fallback;
}

// POST/DELETE that throws the API's error message on failure.
async function mutate(path: string, method = "POST", body?: object): Promise<{ status: string }> {
  const res = await req(path, {
    method,
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let msg = "Something went wrong.";
    try {
      const data = await res.json();
      if (typeof data.detail === "string") msg = data.detail;
    } catch {
      /* non-JSON */
    }
    throw new Error(msg);
  }
  return res.json();
}

export const searchUsers = (q: string): Promise<PublicUser[]> =>
  req(`/users/search?q=${encodeURIComponent(q)}`).then((r) => asJson(r, []));

export const getProfile = (id: string): Promise<PublicUser | null> =>
  req(`/users/${id}`).then((r) => asJson<PublicUser | null>(r, null));

export const getUserSaved = (id: string): Promise<Card[]> =>
  req(`/users/${id}/saved`).then((r) => asJson(r, []));

export const listFriends = (): Promise<PublicUser[]> =>
  req("/friends").then((r) => asJson(r, []));

export const listRequests = (): Promise<PublicUser[]> =>
  req("/friends/requests").then((r) => asJson(r, []));

export const sendRequest = (id: string) => mutate(`/friends/request/${id}`);
export const acceptRequest = (id: string) => mutate(`/friends/accept/${id}`);
export const declineRequest = (id: string) => mutate(`/friends/decline/${id}`);
export const removeFriend = (id: string) => mutate(`/friends/${id}`, "DELETE");

export const shareEvent = (toUserId: string, itemId: string, message?: string) =>
  mutate("/share", "POST", { to_user_id: toUserId, item_id: itemId, message: message || null });

export const listShared = (): Promise<SharedEvent[]> =>
  req("/me/shared").then((r) => asJson(r, []));

export const dismissShared = (shareId: string) => mutate(`/me/shared/${shareId}`, "DELETE");

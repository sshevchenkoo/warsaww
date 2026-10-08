"use client";

import Link from "next/link";
import { useState } from "react";

import { Avatar } from "@/components/Avatar";
import { Icon } from "@/components/Icon";
import {
  acceptRequest,
  declineRequest,
  removeFriend,
  sendRequest,
  type Friendship,
  type PublicUser,
} from "@/lib/social";

const ringBtn =
  "rounded-full px-3 py-1.5 font-mono text-xs tracking-wide transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50";

/** A user row: avatar + name (links to their profile) + the relevant friend action. */
export function UserCard({
  person,
  onChange,
}: {
  person: PublicUser;
  onChange?: (id: string, next: Friendship) => void;
}) {
  const [rel, setRel] = useState<Friendship>(person.friendship);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function act(fn: () => Promise<unknown>, next: Friendship) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      setRel(next);
      onChange?.(person.id, next);
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't update this friendship.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="border-b border-line py-3">
      <div className="flex items-center gap-3">
      <Link href={`/u/${person.id}`} className="flex min-w-0 flex-1 items-center gap-3">
        <Avatar src={person.avatar_url} name={person.name} size={36} online={person.online} />
        <span className="truncate font-bold tracking-tight">{person.name ?? "user"}</span>
      </Link>

      <div className="flex shrink-0 items-center gap-2">
        {rel === "none" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => act(() => sendRequest(person.id), "request_sent")}
            className={`${ringBtn} bg-accent text-accent-ink hover:opacity-90`}
          >
            add friend
          </button>
        )}
        {rel === "request_sent" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => act(() => removeFriend(person.id), "none")}
            className={`${ringBtn} border border-line text-muted hover:text-fg`}
          >
            requested · cancel
          </button>
        )}
        {rel === "request_received" && (
          <>
            <button
              type="button"
              disabled={busy}
              onClick={() => act(() => acceptRequest(person.id), "friends")}
              className={`${ringBtn} bg-accent text-accent-ink hover:opacity-90`}
            >
              accept
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => act(() => declineRequest(person.id), "none")}
              className={`${ringBtn} border border-line text-muted hover:text-accent`}
            >
              decline
            </button>
          </>
        )}
        {rel === "friends" && (
          <button
            type="button"
            disabled={busy}
            onClick={() => act(() => removeFriend(person.id), "none")}
            className={`${ringBtn} inline-flex items-center gap-1 border border-line text-muted hover:text-accent`}
            title="Remove friend"
          >
            friends <Icon name="check" size={12} />
          </button>
        )}
        </div>
      </div>
      {error && (
        <p role="alert" className="mt-1 pl-12 font-mono text-xs text-red-500">
          {error}
        </p>
      )}
    </div>
  );
}

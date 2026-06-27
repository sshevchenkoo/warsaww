"use client";

import Link from "next/link";
import { useState } from "react";

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

  async function act(fn: () => Promise<unknown>, next: Friendship) {
    setBusy(true);
    try {
      await fn();
      setRel(next);
      onChange?.(person.id, next);
    } catch {
      /* keep current state on error */
    } finally {
      setBusy(false);
    }
  }

  const initial = (person.name ?? "?").charAt(0).toUpperCase();

  return (
    <div className="flex items-center gap-3 border-b border-line py-3">
      <Link href={`/u/${person.id}`} className="flex min-w-0 flex-1 items-center gap-3">
        {person.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={person.avatar_url}
            alt=""
            width={36}
            height={36}
            className="h-9 w-9 shrink-0 rounded-full border border-line object-cover"
          />
        ) : (
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent text-sm font-black text-accent-ink">
            {initial}
          </span>
        )}
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
            className={`${ringBtn} border border-line text-muted hover:text-accent`}
            title="Remove friend"
          >
            friends ✓
          </button>
        )}
      </div>
    </div>
  );
}

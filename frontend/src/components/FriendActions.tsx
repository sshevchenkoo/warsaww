"use client";

import { useState } from "react";

import { Icon } from "@/components/Icon";
import {
  acceptRequest,
  declineRequest,
  removeFriend,
  sendRequest,
  type Friendship,
} from "@/lib/social";

const rowBtn =
  "rounded-full px-3 py-1.5 font-mono text-xs tracking-wide transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50";

const profileBtn =
  "rounded-full px-4 py-2 font-mono text-sm tracking-wide transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50";

/** Friend request buttons for one person. `row` matches a people-list card; `profile` matches the hero on /u/[id]. */
export function FriendActions({
  userId,
  friendship,
  onChange,
  variant = "row",
}: {
  userId: string;
  friendship: Friendship;
  onChange: (next: Friendship) => void;
  variant?: "row" | "profile";
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const btn = variant === "profile" ? profileBtn : rowBtn;
  const accent = variant === "profile" ? " font-bold" : "";
  const check = variant === "profile" ? 14 : 12;

  async function act(fn: () => Promise<unknown>, next: Friendship) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChange(next);
    } catch (err) {
      setError(
        err instanceof Error && err.message ? err.message : "Couldn't update this friendship.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (friendship === "self") return null;

  const alert = error ? (
    <p
      role="alert"
      className={
        variant === "profile"
          ? "w-full font-mono text-xs text-red-500"
          : "mt-1 w-full pl-12 font-mono text-xs text-red-500"
      }
    >
      {error}
    </p>
  ) : null;

  const buttons = (
    <div
      className={
        variant === "profile"
          ? "contents"
          : "flex shrink-0 items-center gap-2"
      }
    >
      {friendship === "none" && (
        <button
          type="button"
          disabled={busy}
          onClick={() => act(() => sendRequest(userId), "request_sent")}
          className={`${btn}${accent} bg-accent text-accent-ink hover:opacity-90`}
        >
          add friend
        </button>
      )}
      {friendship === "request_sent" && (
        <button
          type="button"
          disabled={busy}
          onClick={() => act(() => removeFriend(userId), "none")}
          className={`${btn} border border-line text-muted hover:text-fg`}
        >
          requested · cancel
        </button>
      )}
      {friendship === "request_received" && (
        <>
          <button
            type="button"
            disabled={busy}
            onClick={() => act(() => acceptRequest(userId), "friends")}
            className={`${btn}${accent} bg-accent text-accent-ink hover:opacity-90`}
          >
            accept
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => act(() => declineRequest(userId), "none")}
            className={`${btn} border border-line text-muted hover:text-accent`}
          >
            decline
          </button>
        </>
      )}
      {friendship === "friends" && (
        <button
          type="button"
          disabled={busy}
          onClick={() => act(() => removeFriend(userId), "none")}
          className={`${btn} inline-flex items-center gap-1 border border-line text-muted hover:text-accent`}
          title={variant === "row" ? "Remove friend" : undefined}
        >
          friends <Icon name="check" size={check} />
        </button>
      )}
    </div>
  );

  // The row alert is a sibling of the name link, so it can span the card.
  // The profile alert stays in the hero's wrapping button group.
  if (variant === "row") {
    return (
      <>
        {buttons}
        {alert}
      </>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      {buttons}
      {alert}
    </div>
  );
}

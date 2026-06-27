"use client";

import Link from "next/link";
import { useState } from "react";

import { useUser } from "@/components/UserContext";
import { listFriends, shareEvent, type PublicUser } from "@/lib/social";

/** Share an item with a friend. `compact` renders the round icon used on cards;
 *  otherwise a labelled pill for the detail page. Only shown to logged-in users. */
export function ShareButton({ itemId, compact = false }: { itemId: string; compact?: boolean }) {
  const { user } = useUser();
  const [open, setOpen] = useState(false);
  const [friends, setFriends] = useState<PublicUser[] | null>(null);
  const [sent, setSent] = useState<Set<string>>(new Set());

  if (!user) return null;

  function toggle(e: React.MouseEvent) {
    // Cards wrap the content in a <Link>; don't navigate when opening the menu.
    e.preventDefault();
    e.stopPropagation();
    const next = !open;
    setOpen(next);
    if (next && friends === null) listFriends().then(setFriends);
  }

  async function share(e: React.MouseEvent, friendId: string) {
    e.preventDefault();
    e.stopPropagation();
    try {
      await shareEvent(friendId, itemId);
      setSent((prev) => new Set(prev).add(friendId));
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="relative">
      <button
        type="button"
        onClick={toggle}
        aria-label="Share with a friend"
        aria-expanded={open}
        className={
          compact
            ? "grid h-9 w-9 place-items-center rounded-full border border-white/25 bg-black/40 text-base backdrop-blur-sm transition-transform hover:scale-110 active:scale-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
            : "inline-flex items-center gap-1 rounded-full border border-line px-4 py-2.5 font-mono text-sm tracking-wide transition-colors hover:border-accent hover:text-fg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
        }
      >
        {compact ? "↗" : "share ↗"}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-52 overflow-hidden rounded-xl border border-line bg-card shadow-xl">
          <p className="border-b border-line px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-muted">
            share with
          </p>
          {friends === null ? (
            <p className="px-3 py-3 font-mono text-xs text-muted">loading…</p>
          ) : friends.length === 0 ? (
            <Link
              href="/people"
              onClick={(e) => e.stopPropagation()}
              className="block px-3 py-3 font-mono text-xs text-accent"
            >
              add friends to share →
            </Link>
          ) : (
            <ul className="max-h-60 overflow-y-auto">
              {friends.map((f) => (
                <li key={f.id}>
                  <button
                    type="button"
                    onClick={(e) => share(e, f.id)}
                    disabled={sent.has(f.id)}
                    className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-white/5 disabled:opacity-60"
                  >
                    <span className="truncate">{f.name ?? "user"}</span>
                    <span className="shrink-0 font-mono text-[11px] text-accent">
                      {sent.has(f.id) ? "sent ✓" : "send"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

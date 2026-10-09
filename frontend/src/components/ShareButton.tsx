"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

import { Icon, Spinner } from "@/components/Icon";
import { useUser } from "@/components/UserContext";
import { listFriends, shareEvent, type PublicUser } from "@/lib/social";

// One friend list and one open menu for every card. Each button used to fetch
// /friends on open and stay open beside the others.
let friendsCache: PublicUser[] | null = null;
let friendsUserId: string | null = null;
let friendsInflight: Promise<void> | null = null;
// Per button, not per event: the same event can be on screen twice.
let openMenuId: string | null = null;
const menuListeners = new Set<() => void>();

function notifyMenus() {
  menuListeners.forEach((fn) => fn());
}

/** Share an item with a friend. `compact` renders the round icon used on cards;
 *  otherwise a labelled pill for the detail page. Only shown to logged-in users. */
export function ShareButton({ itemId, compact = false }: { itemId: string; compact?: boolean }) {
  const { user } = useUser();
  const menuId = useId();
  const rootRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [friends, setFriends] = useState<PublicUser[] | null>(null);
  const [sent, setSent] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    function sync() {
      setOpen(openMenuId === menuId);
      setFriends(friendsUserId === user?.id ? friendsCache : null);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape" || openMenuId !== menuId) return;
      openMenuId = null;
      notifyMenus();
    }
    function onPointer(e: PointerEvent) {
      // Only the instance that is actually open may dismiss.
      if (openMenuId !== menuId) return;
      if (rootRef.current?.contains(e.target as Node)) return;
      openMenuId = null;
      notifyMenus();
    }
    menuListeners.add(sync);
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      menuListeners.delete(sync);
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [menuId, user?.id]);

  useEffect(() => {
    const id = user?.id ?? null;
    if (friendsUserId === id) return;
    friendsUserId = id;
    friendsCache = null;
    friendsInflight = null;
    openMenuId = null;
    notifyMenus();
  }, [user?.id]);

  if (!user) return null;

  function toggle(e: React.MouseEvent) {
    // Cards wrap the content in a <Link>; don't navigate when opening the menu.
    e.preventDefault();
    e.stopPropagation();
    if (!user) return;
    const next = openMenuId !== menuId;
    openMenuId = next ? menuId : null;
    if (friendsUserId !== user.id) {
      friendsUserId = user.id;
      friendsCache = null;
      friendsInflight = null;
    }
    notifyMenus();
    if (!next || friendsCache || friendsInflight) return;
    const userId = user.id;
    friendsInflight = listFriends()
      .then((rows) => {
        if (friendsUserId === userId) friendsCache = rows;
      })
      .catch(() => {
        if (friendsUserId === userId) friendsCache = [];
      })
      .finally(() => {
        friendsInflight = null;
        if (friendsUserId === userId) notifyMenus();
      });
  }

  async function share(e: React.MouseEvent, friendId: string) {
    e.preventDefault();
    e.stopPropagation();
    setError(null);
    try {
      await shareEvent(friendId, itemId);
      setSent((prev) => new Set(prev).add(friendId));
    } catch (err) {
      setError(err instanceof Error && err.message ? err.message : "Couldn't share this.");
    }
  }

  return (
    <div className="relative" ref={rootRef}>
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
        {!compact && "share"}
        <Icon name="share" size={compact ? 16 : 14} />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-52 overflow-hidden rounded-xl border border-line bg-card shadow-xl">
          <p className="border-b border-line px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-muted">
            share with
          </p>
          {error && (
            <p role="alert" className="border-b border-line px-3 py-2 font-mono text-[11px] text-red-500">
              {error}
            </p>
          )}
          {friends === null ? (
            <p className="flex items-center gap-2 px-3 py-3 font-mono text-xs text-muted">
              <Spinner size={12} />
              loading…
            </p>
          ) : friends.length === 0 ? (
            <Link
              href="/people"
              onClick={(e) => e.stopPropagation()}
              className="flex items-center gap-1 px-3 py-3 font-mono text-xs text-accent"
            >
              add friends to share
              <Icon name="arrow-right" size={12} />
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
                    <span className="inline-flex shrink-0 items-center gap-1 font-mono text-[11px] text-accent">
                      {sent.has(f.id) ? (
                        <>
                          sent <Icon name="check" size={12} />
                        </>
                      ) : (
                        "send"
                      )}
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

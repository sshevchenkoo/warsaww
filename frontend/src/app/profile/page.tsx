"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { EventCard } from "@/components/EventCard";
import { useUser } from "@/components/UserContext";
import { VerifyPanel } from "@/components/VerifyPanel";
import type { Card } from "@/lib/api";
import { getSaved, uploadAvatar } from "@/lib/auth";
import { dismissShared, listShared, type SharedEvent } from "@/lib/social";

export default function Profile() {
  const { user, loading, savedIds, updateUser } = useUser();
  const [cards, setCards] = useState<Card[]>([]);
  const [shared, setShared] = useState<SharedEvent[]>([]);
  const [busy, setBusy] = useState(true);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  async function onPickAvatar(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // let the same file be re-picked after an error
    if (!file) return;
    setAvatarError(null);
    setAvatarBusy(true);
    try {
      const url = await uploadAvatar(file);
      updateUser({ avatar_url: url });
    } catch (err) {
      setAvatarError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setAvatarBusy(false);
    }
  }

  useEffect(() => {
    if (!user) return; // logged-out renders the sign-in prompt; busy is unused there
    getSaved().then((c) => {
      setCards(c);
      setBusy(false);
    });
    listShared().then(setShared);
  }, [user]);

  function dismiss(shareId: string) {
    setShared((prev) => prev.filter((s) => s.id !== shareId));
    dismissShared(shareId).catch(() => {});
  }

  if (loading) return null;

  if (!user) {
    return (
      <main className="mx-auto w-full max-w-6xl px-5 pb-24 pt-16">
        <h1 className="text-4xl font-black tracking-tighter sm:text-5xl">your saved</h1>
        <p className="mt-3 max-w-md font-mono text-sm text-muted">
          sign in to keep the events &amp; places you like.
        </p>
        <Link
          href="/login"
          className="mt-6 inline-block rounded-full bg-accent px-4 py-2 font-mono text-sm font-bold text-accent-ink transition-transform hover:scale-105 active:scale-95"
        >
          sign in
        </Link>
      </main>
    );
  }

  // Reflect un-hearting live: only show cards still in savedIds.
  const visible = cards.filter((c) => savedIds.has(c.id));

  return (
    <main className="mx-auto w-full max-w-6xl px-5 pb-24 pt-10 sm:pt-14">
      <header className="mb-8 flex items-center gap-4">
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          disabled={avatarBusy}
          className="group relative h-14 w-14 shrink-0 rounded-full"
          aria-label="Change profile photo"
          title="Change profile photo"
        >
          {user.avatar_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={user.avatar_url}
              alt=""
              width={56}
              height={56}
              className="h-14 w-14 rounded-full border border-line object-cover"
            />
          ) : (
            <span className="grid h-14 w-14 place-items-center rounded-full bg-accent text-2xl font-black text-accent-ink">
              {(user.name ?? user.email ?? "?").charAt(0).toUpperCase()}
            </span>
          )}
          <span className="absolute inset-0 grid place-items-center rounded-full bg-black/50 font-mono text-[9px] uppercase tracking-wide text-white opacity-0 transition-opacity group-hover:opacity-100">
            {avatarBusy ? "…" : "edit"}
          </span>
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          className="hidden"
          onChange={onPickAvatar}
        />
        <div className="min-w-0">
          <h1 className="truncate text-3xl font-black tracking-tighter sm:text-4xl">
            {user.name ?? "your saved"}
          </h1>
          {user.email && (
            <p className="font-mono text-xs tracking-wide text-muted">{user.email}</p>
          )}
          {avatarError && (
            <p className="mt-1 font-mono text-xs text-red-500">{avatarError}</p>
          )}
        </div>
        <Link
          href="/people"
          className="ml-auto shrink-0 rounded-full border border-line px-3.5 py-1.5 font-mono text-xs tracking-wide text-muted transition-colors hover:border-accent hover:text-fg"
        >
          people →
        </Link>
      </header>

      {/* Unconfirmed email: the code-entry form lives here so a user who left the
          signup page can still verify (and unlock search) from their profile. */}
      {!user.email_verified && (
        <section className="mb-10">
          <VerifyPanel />
        </section>
      )}

      {shared.length > 0 && (
        <section className="mb-10">
          <h2 className="mb-4 font-mono text-[11px] uppercase tracking-widest text-accent">
            shared with you
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
            {shared.map((s, i) => (
              <div key={s.id}>
                <p className="mb-1 flex items-center justify-between gap-2 font-mono text-[10px] tracking-wide text-muted">
                  <span className="truncate">from {s.from_user.name ?? "a friend"}</span>
                  <button
                    type="button"
                    onClick={() => dismiss(s.id)}
                    className="shrink-0 transition-colors hover:text-accent"
                    aria-label="Dismiss"
                  >
                    ✕
                  </button>
                </p>
                <EventCard card={s.item} index={i} />
              </div>
            ))}
          </div>
        </section>
      )}

      <h2 className="mb-4 font-mono text-[11px] uppercase tracking-widest text-muted">
        your saved
      </h2>
      {busy ? (
        <p className="flex items-center gap-2 font-mono text-sm text-muted">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" />
          loading your saved…
        </p>
      ) : visible.length === 0 ? (
        <p className="font-mono text-sm text-muted">
          nothing saved yet — tap the ♡ on a card to keep it here.
        </p>
      ) : (
        <section className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
          {visible.map((card, i) => (
            <EventCard key={card.id} card={card} index={i} />
          ))}
        </section>
      )}
    </main>
  );
}

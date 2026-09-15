"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Avatar } from "@/components/Avatar";
import { CardSkeleton } from "@/components/CardSkeleton";
import { EmptyState } from "@/components/EmptyState";
import { EventCard } from "@/components/EventCard";
import { SectionHeading } from "@/components/SectionHeading";
import { useUser } from "@/components/UserContext";
import { VerifyPanel } from "@/components/VerifyPanel";
import type { Card } from "@/lib/api";
import { getSaved, uploadAvatar } from "@/lib/auth";
import {
  dismissShared,
  listFriends,
  listShared,
  type PublicUser,
  type SharedEvent,
} from "@/lib/social";

/** One number + its label in the hero's stat strip. */
function Stat({ value, label, href }: { value: number; label: string; href?: string }) {
  const inner = (
    <>
      <dt className="text-2xl font-black tabular-nums tracking-tighter sm:text-3xl">{value}</dt>
      <dd className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-muted">
        {label}
      </dd>
    </>
  );
  return href ? (
    <Link href={href} className="group block transition-colors hover:text-accent">
      {inner}
    </Link>
  ) : (
    <div>{inner}</div>
  );
}

export default function Profile() {
  const { user, loading, savedIds, updateUser } = useUser();
  const [cards, setCards] = useState<Card[]>([]);
  const [shared, setShared] = useState<SharedEvent[]>([]);
  const [friends, setFriends] = useState<PublicUser[]>([]);
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
    listFriends().then(setFriends);
  }, [user]);

  function dismiss(shareId: string) {
    setShared((prev) => prev.filter((s) => s.id !== shareId));
    dismissShared(shareId).catch(() => {});
  }

  if (loading) return null;

  if (!user) {
    return (
      <main className="mx-auto grid w-full max-w-6xl place-items-center px-5 pb-24 pt-24 text-center">
        <span aria-hidden className="text-4xl text-muted/40">
          ♡
        </span>
        <h1 className="mt-4 text-4xl font-black tracking-tighter sm:text-5xl">
          your saved<span className="text-accent">.</span>
        </h1>
        <p className="mt-3 max-w-sm font-mono text-sm leading-relaxed text-muted">
          sign in to keep the events &amp; places you like — and to see what friends
          send your way.
        </p>
        <Link
          href="/login"
          className="mt-7 rounded-full bg-accent px-5 py-2.5 font-mono text-sm font-bold text-accent-ink transition-transform hover:scale-105 active:scale-95"
        >
          sign in
        </Link>
      </main>
    );
  }

  // Reflect un-hearting live: only show cards still in savedIds.
  const visible = cards.filter((c) => savedIds.has(c.id));
  const displayName = user.name ?? user.email?.split("@")[0] ?? "you";

  return (
    <main className="mx-auto w-full max-w-6xl px-5 pb-24 pt-6 sm:pt-10">
      {/* ─── Hero ─────────────────────────────────────────────────────────── */}
      <section className="relative overflow-hidden rounded-3xl border border-line bg-card">
        {/* Accent wash: a soft radial bloom behind the avatar, so the hero reads
            as a band without introducing a second color to the palette. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.16]"
          style={{
            background:
              "radial-gradient(60% 120% at 12% 0%, var(--color-accent) 0%, transparent 62%)",
          }}
        />

        <div className="relative flex flex-col gap-6 p-6 sm:p-8">
          <div className="flex items-start gap-5">
            <div className="relative shrink-0">
              <button
                type="button"
                onClick={() => fileInput.current?.click()}
                disabled={avatarBusy}
                className="group relative block rounded-full"
                aria-label="Change profile photo"
                title="Change profile photo"
              >
                <Avatar src={user.avatar_url} name={displayName} size={88} ring />
                <span className="absolute inset-0 grid place-items-center rounded-full bg-black/55 font-mono text-[10px] uppercase tracking-widest text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                  {avatarBusy ? "…" : "change"}
                </span>
              </button>
              {/* A visible affordance as well as the hover overlay — on touch
                  there is no hover, so the overlay alone is undiscoverable. */}
              <span
                aria-hidden
                className="pointer-events-none absolute -bottom-0.5 -right-0.5 grid h-7 w-7 place-items-center rounded-full border-2 border-card bg-accent text-xs text-accent-ink"
              >
                {avatarBusy ? "…" : "✎"}
              </span>
            </div>

            <div className="min-w-0 flex-1 pt-1">
              <h1 className="truncate text-3xl font-black tracking-tighter sm:text-4xl">
                {displayName}
              </h1>
              <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1.5">
                {user.email && (
                  <span className="truncate font-mono text-xs tracking-wide text-muted">
                    {user.email}
                  </span>
                )}
                <span
                  className={`rounded-full px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest ${
                    user.email_verified
                      ? "bg-accent/15 text-accent"
                      : "border border-line text-muted"
                  }`}
                >
                  {user.email_verified ? "verified ✓" : "unverified"}
                </span>
              </div>
              {avatarError && (
                <p role="alert" className="mt-2 font-mono text-xs text-red-500">
                  {avatarError}
                </p>
              )}
            </div>

            <Link
              href="/people"
              className="ml-auto hidden shrink-0 rounded-full border border-line px-4 py-2 font-mono text-xs tracking-wide text-muted transition-colors hover:border-accent hover:text-fg sm:block"
            >
              people →
            </Link>
          </div>

          <input
            ref={fileInput}
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            className="hidden"
            onChange={onPickAvatar}
          />

          {/* ─── Stats ──────────────────────────────────────────────────── */}
          <dl className="grid grid-cols-3 divide-x divide-line border-t border-line pt-5">
            <div className="pr-4">
              <Stat value={visible.length} label="saved" />
            </div>
            <div className="px-4">
              <Stat value={friends.length} label="friends" href="/people" />
            </div>
            <div className="pl-4">
              <Stat value={shared.length} label="shared with you" />
            </div>
          </dl>
        </div>
      </section>

      {/* Unconfirmed email: the code-entry form lives here so a user who left the
          signup page can still verify (and unlock search) from their profile. */}
      {!user.email_verified && (
        <section className="mt-8">
          <VerifyPanel />
        </section>
      )}

      {shared.length > 0 && (
        <section className="mt-10">
          <SectionHeading label="shared with you" count={shared.length} accent />
          <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
            {shared.map((s, i) => (
              <div key={s.id} className="group/share">
                <div className="mb-2 flex items-center gap-2">
                  <Link
                    href={`/u/${s.from_user.id}`}
                    className="flex min-w-0 flex-1 items-center gap-2 transition-colors hover:text-accent"
                  >
                    <Avatar
                      src={s.from_user.avatar_url}
                      name={s.from_user.name}
                      size={20}
                    />
                    <span className="truncate font-mono text-[10px] tracking-wide text-muted">
                      {s.from_user.name ?? "a friend"}
                    </span>
                  </Link>
                  <button
                    type="button"
                    onClick={() => dismiss(s.id)}
                    className="grid h-6 w-6 shrink-0 place-items-center rounded-full text-muted opacity-0 transition-all hover:bg-line hover:text-accent focus-visible:opacity-100 group-hover/share:opacity-100"
                    aria-label={`Dismiss ${s.item.name}`}
                    title="Dismiss"
                  >
                    ✕
                  </button>
                </div>
                {s.message && (
                  <p className="mb-2 line-clamp-2 border-l-2 border-accent/50 pl-2 font-mono text-[11px] leading-relaxed text-muted">
                    {s.message}
                  </p>
                )}
                <EventCard card={s.item} index={i} />
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="mt-10">
        <SectionHeading label="your saved" count={busy ? undefined : visible.length} />
        {busy ? (
          <CardSkeleton />
        ) : visible.length === 0 ? (
          <EmptyState
            glyph="♡"
            title="nothing saved yet"
            body="tap the heart on any card and it lands here, ready for the weekend."
            href="/"
            cta="find something →"
          />
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
            {visible.map((card, i) => (
              <EventCard key={card.id} card={card} index={i} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

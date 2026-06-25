"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { EventCard } from "@/components/EventCard";
import { useUser } from "@/components/UserContext";
import type { Card } from "@/lib/api";
import { getSaved } from "@/lib/auth";

export default function Profile() {
  const { user, loading, savedIds } = useUser();
  const [cards, setCards] = useState<Card[]>([]);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    if (!user) return; // logged-out renders the sign-in prompt; busy is unused there
    getSaved().then((c) => {
      setCards(c);
      setBusy(false);
    });
  }, [user]);

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
        <div>
          <h1 className="text-3xl font-black tracking-tighter sm:text-4xl">
            {user.name ?? "your saved"}
          </h1>
          {user.email && (
            <p className="font-mono text-xs tracking-wide text-muted">{user.email}</p>
          )}
        </div>
      </header>

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

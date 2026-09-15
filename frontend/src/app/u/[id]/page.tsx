"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Avatar } from "@/components/Avatar";
import { EmptyState } from "@/components/EmptyState";
import { EventCard } from "@/components/EventCard";
import { SectionHeading } from "@/components/SectionHeading";
import { useUser } from "@/components/UserContext";
import type { Card } from "@/lib/api";
import {
  acceptRequest,
  declineRequest,
  getProfile,
  getUserSaved,
  removeFriend,
  sendRequest,
  type Friendship,
  type PublicUser,
} from "@/lib/social";

const btn =
  "rounded-full px-4 py-2 font-mono text-sm tracking-wide transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent disabled:opacity-50";

export default function Profile() {
  const { id } = useParams<{ id: string }>();
  const { user, loading: meLoading } = useUser();
  // undefined = loading, null = not found
  const [person, setPerson] = useState<PublicUser | null | undefined>(undefined);
  const [rel, setRel] = useState<Friendship>("none");
  const [saved, setSaved] = useState<Card[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!id) return;
    getProfile(id).then((p) => {
      setPerson(p);
      if (p) setRel(p.friendship);
    });
  }, [id]);

  // (Re)load saved whenever we become friends (or it's our own profile). The
  // saved section only renders for friends/self, so no need to clear otherwise.
  useEffect(() => {
    if (!id) return;
    if (rel === "friends" || rel === "self") getUserSaved(id).then(setSaved);
  }, [id, rel]);

  if (meLoading || person === undefined) {
    return (
      <main className="mx-auto w-full max-w-6xl px-5 pt-10">
        <div className="h-40 animate-pulse rounded-3xl border border-line bg-card" />
      </main>
    );
  }

  if (!user) {
    return (
      <main className="mx-auto w-full max-w-6xl px-5 pt-16">
        <p className="font-mono text-sm text-muted">sign in to view profiles.</p>
        <Link href="/login" className="mt-4 inline-block font-mono text-xs text-accent">
          sign in →
        </Link>
      </main>
    );
  }

  if (person === null) {
    return (
      <main className="mx-auto w-full max-w-6xl px-5 pt-16">
        <h1 className="text-3xl font-black tracking-tighter">user not found</h1>
        <Link href="/people" className="mt-4 inline-block font-mono text-xs text-accent">
          ← back to people
        </Link>
      </main>
    );
  }

  async function act(fn: () => Promise<unknown>, next: Friendship) {
    setBusy(true);
    try {
      await fn();
      setRel(next);
    } catch {
      /* ignore */
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-6xl px-5 pb-24 pt-6 sm:pt-10">
      <Link
        href="/people"
        className="font-mono text-xs tracking-wide text-muted transition-colors hover:text-fg"
      >
        ← people
      </Link>

      {/* Same hero band as /profile, so a profile looks like a profile whoever
          is looking at it. */}
      <section className="relative mt-4 overflow-hidden rounded-3xl border border-line bg-card">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.16]"
          style={{
            background:
              "radial-gradient(60% 120% at 12% 0%, var(--color-accent) 0%, transparent 62%)",
          }}
        />
        <div className="relative flex flex-wrap items-center gap-5 p-6 sm:p-8">
          <Avatar
            src={person.avatar_url}
            name={person.name}
            size={88}
            online={person.online}
            ring
          />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-3xl font-black tracking-tighter sm:text-4xl">
              {person.name ?? "user"}
            </h1>
            <p className="mt-1.5 flex items-center gap-1.5 font-mono text-xs tracking-wide text-muted">
              <span
                className={`inline-block h-2 w-2 rounded-full ${
                  person.online ? "bg-green-500" : "bg-muted/40"
                }`}
              />
              {person.online ? "online" : "offline"}
            </p>
          </div>

          {rel !== "self" && (
            <div className="flex items-center gap-2">
              {rel === "none" && (
                <button type="button" disabled={busy} onClick={() => act(() => sendRequest(person.id), "request_sent")} className={`${btn} bg-accent font-bold text-accent-ink hover:opacity-90`}>
                  add friend
                </button>
              )}
              {rel === "request_sent" && (
                <button type="button" disabled={busy} onClick={() => act(() => removeFriend(person.id), "none")} className={`${btn} border border-line text-muted hover:text-fg`}>
                  requested · cancel
                </button>
              )}
              {rel === "request_received" && (
                <>
                  <button type="button" disabled={busy} onClick={() => act(() => acceptRequest(person.id), "friends")} className={`${btn} bg-accent font-bold text-accent-ink hover:opacity-90`}>
                    accept
                  </button>
                  <button type="button" disabled={busy} onClick={() => act(() => declineRequest(person.id), "none")} className={`${btn} border border-line text-muted hover:text-accent`}>
                    decline
                  </button>
                </>
              )}
              {rel === "friends" && (
                <button type="button" disabled={busy} onClick={() => act(() => removeFriend(person.id), "none")} className={`${btn} border border-line text-muted hover:text-accent`}>
                  friends ✓
                </button>
              )}
            </div>
          )}
        </div>
      </section>

      {rel === "friends" || rel === "self" ? (
        <section className="mt-10">
          <SectionHeading label="saved" count={saved.length} />
          {saved.length === 0 ? (
            <EmptyState
              glyph="♡"
              title="nothing saved yet"
              body={`${person.name ?? "this user"} hasn't kept anything here so far.`}
            />
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
              {saved.map((card, i) => (
                <EventCard key={card.id} card={card} index={i} />
              ))}
            </div>
          )}
        </section>
      ) : (
        <section className="mt-10">
          <EmptyState
            glyph="🔒"
            title="saved list is private"
            body={`add ${person.name ?? "this user"} as a friend to see the events and places they keep.`}
          />
        </section>
      )}
    </main>
  );
}

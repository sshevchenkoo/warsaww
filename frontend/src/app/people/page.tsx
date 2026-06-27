"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { UserCard } from "@/components/UserCard";
import { useUser } from "@/components/UserContext";
import {
  listFriends,
  listRequests,
  searchUsers,
  type PublicUser,
} from "@/lib/social";

export default function People() {
  const { user, loading } = useUser();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PublicUser[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [requests, setRequests] = useState<PublicUser[]>([]);
  const [friends, setFriends] = useState<PublicUser[]>([]);

  useEffect(() => {
    if (!user) return;
    listRequests().then(setRequests);
    listFriends().then(setFriends);
  }, [user]);

  // Debounced search as you type. All state updates happen inside the timeout
  // callback (never synchronously in the effect body).
  useEffect(() => {
    const q = query.trim();
    const id = setTimeout(async () => {
      if (q.length < 2) {
        setResults(null);
        setSearching(false);
        return;
      }
      setSearching(true);
      setResults(await searchUsers(q));
      setSearching(false);
    }, q.length < 2 ? 0 : 300);
    return () => clearTimeout(id);
  }, [query]);

  if (loading) return null;

  if (!user) {
    return (
      <main className="mx-auto w-full max-w-2xl px-5 pb-24 pt-16">
        <h1 className="text-4xl font-black tracking-tighter">people</h1>
        <p className="mt-3 font-mono text-sm text-muted">
          sign in to find friends and share events.
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

  // When a search-result relationship changes, refresh the friends/requests lists.
  const refreshLists = () => {
    listRequests().then(setRequests);
    listFriends().then(setFriends);
  };

  return (
    <main className="mx-auto w-full max-w-2xl px-5 pb-24 pt-10 sm:pt-14">
      <h1 className="mb-6 text-4xl font-black tracking-tighter sm:text-5xl">people</h1>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="search by name or email…"
        aria-label="Search people"
        className="w-full border-b-2 border-line bg-transparent pb-2 text-lg font-bold tracking-tight transition-colors placeholder:text-muted/70 focus:border-accent"
      />

      <div role="status" aria-live="polite">
        {results !== null && (
          <section className="mt-4">
            {searching && <p className="font-mono text-xs text-muted">searching…</p>}
            {!searching && results.length === 0 && (
              <p className="font-mono text-xs text-muted">no one matched “{query.trim()}”.</p>
            )}
            {results.map((p) => (
              <UserCard key={p.id} person={p} onChange={refreshLists} />
            ))}
          </section>
        )}
      </div>

      {results === null && (
        <>
          {requests.length > 0 && (
            <section className="mt-10">
              <h2 className="mb-2 font-mono text-[11px] uppercase tracking-widest text-accent">
                friend requests
              </h2>
              {requests.map((p) => (
                <UserCard key={p.id} person={p} onChange={refreshLists} />
              ))}
            </section>
          )}

          <section className="mt-10">
            <h2 className="mb-2 font-mono text-[11px] uppercase tracking-widest text-muted">
              friends ({friends.length})
            </h2>
            {friends.length === 0 ? (
              <p className="font-mono text-xs text-muted">
                no friends yet — search above to add some.
              </p>
            ) : (
              friends.map((p) => <UserCard key={p.id} person={p} onChange={refreshLists} />)
            )}
          </section>
        </>
      )}
    </main>
  );
}

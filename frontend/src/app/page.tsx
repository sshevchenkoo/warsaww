"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { EventCard } from "@/components/EventCard";
import { useUser } from "@/components/UserContext";
import { VerifyPanel } from "@/components/VerifyPanel";
import { getUpcoming, streamSearch, type Card, type Intent } from "@/lib/api";

const EXAMPLES = [
  "museum about Chopin",
  "techno party this weekend",
  "spokojny spacer nad wodą",
  "cheap night out on Saturday",
  "where to take a date tonight",
];

type Status = "idle" | "loading" | "streaming" | "done" | "error" | "limited";

export default function Home() {
  const [query, setQuery] = useState("");
  const [cards, setCards] = useState<Card[]>([]);
  const [intent, setIntent] = useState<Intent | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [placeholder, setPlaceholder] = useState(EXAMPLES[0]);
  const [upcoming, setUpcoming] = useState<Card[]>([]);
  const [limitMsg, setLimitMsg] = useState("");
  // The text of the last query we actually searched. Used to make a repeated
  // Enter on the same, unchanged prompt a no-op instead of firing a fresh
  // /search each time (every submit is a real request against the rate limit
  // and the LLM). Cleared on error so a failed search can still be retried.
  const [lastQuery, setLastQuery] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  // Search is gated: only a logged-in, email-verified user can run prompts.
  const { user, loading: authLoading } = useUser();
  const canSearch = !!user?.email_verified;

  // Load the default "upcoming" feed once on mount.
  useEffect(() => {
    getUpcoming().then(setUpcoming);
  }, []);

  // Cycle the placeholder while the user hasn't typed anything.
  useEffect(() => {
    if (query) return;
    let i = 0;
    const id = setInterval(() => {
      i = (i + 1) % EXAMPLES.length;
      setPlaceholder(EXAMPLES[i]);
    }, 2600);
    return () => clearInterval(id);
  }, [query]);

  async function run(prompt: string) {
    if (!canSearch) return; // gated — the UI shows a sign-in / verify prompt instead
    const text = prompt.trim();
    if (!text) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setLastQuery(text);
    setQuery(text);
    setCards([]);
    setIntent(null);
    setStatus("loading");

    try {
      await streamSearch(text, {
        signal: ctrl.signal,
        onIntent: (it) => {
          setIntent(it);
          setStatus("streaming");
        },
        onCard: (card) => setCards((prev) => [...prev, card]),
        onDone: () => setStatus("done"),
      });
    } catch (err) {
      const e = err as Error;
      if (e.name === "AbortError") return;
      // Let the user retry the same prompt after a failure by pressing Enter
      // again (the dedupe guard below would otherwise treat it as unchanged).
      setLastQuery("");
      if (e.name === "RateLimitError" || e.name === "AuthError") {
        setLimitMsg(e.message);
        setStatus("limited");
      } else {
        setStatus("error");
      }
    }
  }

  const busy = status === "loading" || status === "streaming";
  const chips = intent
    ? [...intent.categories, intent.area].filter((v): v is string => Boolean(v))
    : [];

  return (
    <main className="mx-auto w-full max-w-6xl px-5 pb-24 pt-10 sm:pt-16">
      {/* Wordmark */}
      <header className="mb-10 sm:mb-14">
        <h1 className="text-5xl font-black tracking-tighter sm:text-7xl">
          warsaw<span className="text-accent">,</span>
          <span className="caret text-accent"> _</span>
        </h1>
        <p className="mt-2 max-w-md font-mono text-xs tracking-wide text-muted sm:text-sm">
          type a vibe — get tonight. events &amp; places, ranked for you.
        </p>
      </header>

      {/* Search — gated behind a verified account. While auth is still loading
          render nothing here to avoid flashing the sign-in prompt at a user who
          turns out to be logged in. */}
      {!authLoading && canSearch && (
        <>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              // Enter submits the form even when the button is disabled, so gate here:
              // ignore while a search is in flight, and skip an unchanged prompt so
              // repeated Enter presses don't fire duplicate searches.
              if (busy) return;
              if (query.trim() === lastQuery) return;
              run(query);
            }}
            className="relative"
          >
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={placeholder}
              autoFocus
              aria-label="Search prompt"
              className="w-full border-b-2 border-line bg-transparent pb-3 pr-14 text-2xl font-bold tracking-tight text-fg transition-colors placeholder:text-muted/70 focus:border-accent sm:text-4xl"
            />
            <button
              type="submit"
              aria-label="Search"
              disabled={busy}
              className="absolute bottom-2.5 right-0 grid h-11 w-11 place-items-center rounded-full bg-accent text-accent-ink transition-transform hover:scale-105 active:scale-95 disabled:opacity-50 sm:h-12 sm:w-12"
            >
              <span className="text-xl font-black">{busy ? "·" : "→"}</span>
            </button>
          </form>

          {/* Example chips */}
          {status === "idle" && (
            <div className="mt-6 flex flex-wrap gap-2">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => run(ex)}
                  className="rounded-full border border-line px-3 py-1.5 font-mono text-xs tracking-wide text-muted transition-colors hover:border-accent hover:text-fg"
                >
                  {ex}
                </button>
              ))}
            </div>
          )}
        </>
      )}

      {/* Not signed in: prompt to sign in / create an account. */}
      {!authLoading && !user && (
        <div className="rounded-2xl border border-line p-5 sm:p-6">
          <h2 className="text-xl font-black tracking-tight">
            sign in to search<span className="text-accent">.</span>
          </h2>
          <p className="mt-1 font-mono text-xs tracking-wide text-muted">
            create a free account to write prompts and search events. browsing
            what&apos;s coming up is open to everyone.
          </p>
          <Link
            href="/login"
            className="mt-4 inline-block rounded-full bg-accent px-5 py-2.5 font-bold text-accent-ink transition-transform hover:scale-[1.02] active:scale-95"
          >
            sign in / create account
          </Link>
        </div>
      )}

      {/* Signed in but not verified: enter the emailed code. */}
      {!authLoading && user && !canSearch && <VerifyPanel />}

      {/* Intent read-out */}
      {chips.length > 0 && (
        <div className="mt-6 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[11px] uppercase tracking-widest text-muted">
            read as
          </span>
          {chips.map((c) => (
            <span
              key={c}
              className="rounded-full bg-accent/15 px-2.5 py-1 font-mono text-[11px] tracking-wide text-accent"
            >
              {c}
            </span>
          ))}
        </div>
      )}

      {/* Status line — announced to screen readers as it changes. */}
      <div role="status" aria-live="polite">
        {busy && (
          <p className="mt-8 flex items-center gap-2 font-mono text-sm text-muted">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" />
            {status === "loading" ? "reading the city…" : "ranking your night…"}
          </p>
        )}
        {status === "done" && cards.length === 0 && (
          <p className="mt-8 font-mono text-sm text-muted">
            nothing matched — try a looser vibe.
          </p>
        )}
        {status === "error" && (
          <p className="mt-8 font-mono text-sm text-accent">
            couldn&apos;t reach the city. is the API running on :8000?
          </p>
        )}
        {status === "limited" && (
          <p className="mt-8 font-mono text-sm text-accent">{limitMsg}</p>
        )}
      </div>

      {/* Results grid */}
      {cards.length > 0 && (
        <section className="mt-8 grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
          {cards.map((card, i) => (
            <EventCard key={card.id} card={card} index={i} />
          ))}
        </section>
      )}

      {/* Upcoming feed: sits under the prompt by default, slides below the
          results once the user searches. */}
      {upcoming.length > 0 && (
        <section className="mt-12">
          <h2 className="mb-4 font-mono text-[11px] uppercase tracking-widest text-muted">
            {status === "idle" ? "upcoming" : "also coming up"}
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4">
            {upcoming.map((card, i) => (
              <EventCard key={card.id} card={card} index={i} />
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";

import { EventCard } from "@/components/EventCard";
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
  const abortRef = useRef<AbortController | null>(null);

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
    const text = prompt.trim();
    if (!text) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

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
      if (e.name === "RateLimitError") {
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

      {/* Search */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
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
          className="w-full border-b-2 border-line bg-transparent pb-3 pr-14 text-2xl font-bold tracking-tight text-fg outline-none transition-colors placeholder:text-muted/70 focus:border-accent sm:text-4xl"
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
              onClick={() => run(ex)}
              className="rounded-full border border-line px-3 py-1.5 font-mono text-xs tracking-wide text-muted transition-colors hover:border-accent hover:text-fg"
            >
              {ex}
            </button>
          ))}
        </div>
      )}

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

      {/* Status line */}
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

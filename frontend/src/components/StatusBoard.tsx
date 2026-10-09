"use client";

import { useEffect, useState } from "react";

type Check = "checking" | "up" | "down";

type Probe = {
  api: Check;
  db: Check;
  redis: Check;
  checkedAt: Date | null;
};

const INITIAL: Probe = {
  api: "checking",
  db: "checking",
  redis: "checking",
  checkedAt: null,
};

const REFRESH_MS = 30_000;

const ROWS: { key: keyof Pick<Probe, "api" | "db" | "redis">; label: string }[] = [
  { key: "api", label: "API" },
  { key: "db", label: "Postgres" },
  { key: "redis", label: "Redis" },
];

function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === "AbortError";
}

function asUp(value: unknown): Check {
  return value === true ? "up" : "down";
}

/** /ready is 200 {db, redis} or 503 {detail: {db, redis}}. A proxy 500/502 is not an answer. */
async function readReady(signal: AbortSignal): Promise<{ db: Check; redis: Check; answered: boolean }> {
  try {
    const res = await fetch("/ready", { cache: "no-store", signal });
    const body = (await res.json().catch(() => null)) as
      | { db?: unknown; redis?: unknown; detail?: { db?: unknown; redis?: unknown } }
      | null;
    const payload = res.status === 200 ? body : res.status === 503 ? body?.detail : null;
    if (
      typeof payload !== "object" ||
      payload === null ||
      typeof payload.db !== "boolean" ||
      typeof payload.redis !== "boolean"
    ) {
      return { db: "down", redis: "down", answered: false };
    }
    return { db: asUp(payload.db), redis: asUp(payload.redis), answered: true };
  } catch (err) {
    if (isAbort(err)) throw err;
    return { db: "down", redis: "down", answered: false };
  }
}

async function probe(signal: AbortSignal): Promise<Probe> {
  const checkedAt = new Date();
  let api: Check = "down";
  try {
    const res = await fetch("/health", { cache: "no-store", signal });
    if (res.ok) {
      const body = (await res.json().catch(() => null)) as { status?: unknown } | null;
      api = body?.status === "ok" ? "up" : "down";
    }
  } catch (err) {
    if (isAbort(err)) throw err;
  }

  const ready = await readReady(signal);
  // /health is a process check. If it failed but /ready still answered, the API is up.
  if (api === "down" && ready.answered) api = "up";

  return { api, db: ready.db, redis: ready.redis, checkedAt };
}

function formatChecked(date: Date): string {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).format(date);
}

function StatusWord({ check }: { check: Check }) {
  if (check === "checking") {
    return <span className="text-muted">checking…</span>;
  }
  if (check === "up") {
    return <span className="text-fg">up</span>;
  }
  return <span className="text-red-500">down</span>;
}

export function StatusBoard() {
  const [probeState, setProbeState] = useState<Probe>(INITIAL);

  useEffect(() => {
    let stopped = false;
    let current: AbortController | null = null;

    async function run() {
      current?.abort();
      const controller = new AbortController();
      current = controller;
      try {
        const next = await probe(controller.signal);
        if (!stopped && current === controller) setProbeState(next);
      } catch (err) {
        if (isAbort(err) || stopped || current !== controller) return;
        setProbeState({ api: "down", db: "down", redis: "down", checkedAt: new Date() });
      }
    }

    void run();
    const timer = window.setInterval(() => void run(), REFRESH_MS);
    return () => {
      stopped = true;
      current?.abort();
      window.clearInterval(timer);
    };
  }, []);

  return (
    <section aria-live="polite" className="mt-8 border border-line">
      <ul>
        {ROWS.map((row) => (
          <li
            key={row.key}
            className="flex items-center justify-between gap-4 border-b border-line px-4 py-4 last:border-b-0"
          >
            <span className="text-sm font-black tracking-tight">{row.label}</span>
            <span className="font-mono text-xs tracking-wide">
              <StatusWord check={probeState[row.key]} />
            </span>
          </li>
        ))}
      </ul>
      <p className="border-t border-line px-4 py-3 font-mono text-[11px] tracking-wide text-muted">
        {probeState.checkedAt
          ? `Last checked ${formatChecked(probeState.checkedAt)}. Refreshes every 30 seconds.`
          : "Checking… Refreshes every 30 seconds."}
      </p>
    </section>
  );
}

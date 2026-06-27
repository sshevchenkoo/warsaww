"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { ShareButton } from "@/components/ShareButton";
import { useUser } from "@/components/UserContext";
import { getItem, type Card } from "@/lib/api";
import { categoryLabel, fallbackHue, formatPrice, formatWhen } from "@/lib/format";

export default function ItemPage() {
  const { id } = useParams<{ id: string }>();
  // undefined = loading, null = not found.
  const [item, setItem] = useState<Card | null | undefined>(undefined);
  const [imgError, setImgError] = useState(false);
  const { user, savedIds, toggleSave } = useUser();

  useEffect(() => {
    getItem(id).then(setItem);
  }, [id]);

  if (item === undefined) {
    return (
      <main className="mx-auto w-full max-w-3xl px-5 pt-10">
        <p className="flex items-center gap-2 font-mono text-sm text-muted">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" />
          loading…
        </p>
      </main>
    );
  }

  if (item === null) {
    return (
      <main className="mx-auto w-full max-w-3xl px-5 pt-16">
        <h1 className="text-3xl font-black tracking-tighter">not found</h1>
        <Link href="/" className="mt-4 inline-block font-mono text-xs text-accent">
          ← back to search
        </Link>
      </main>
    );
  }

  const when = formatWhen(item);
  const price = formatPrice(item);
  const hue = fallbackHue(item.id);
  const saved = savedIds.has(item.id);

  return (
    <main className="mx-auto w-full max-w-3xl px-5 pb-24 pt-8">
      <Link
        href="/"
        className="font-mono text-xs tracking-wide text-muted transition-colors hover:text-fg"
      >
        ← back
      </Link>

      <div className="relative mt-5 aspect-[16/9] overflow-hidden rounded-2xl border border-line bg-card">
        {item.image_url && !imgError ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={item.image_url}
            alt=""
            onError={() => setImgError(true)}
            className="absolute inset-0 h-full w-full object-cover"
          />
        ) : (
          <div className="absolute inset-0" style={{ background: `hsl(${hue} 55% 16%)` }} />
        )}
        <div className="absolute left-0 top-0 p-4">
          <span className="rounded-full border border-white/25 bg-black/30 px-2.5 py-1 font-mono text-[10px] font-medium tracking-[0.14em] text-fg backdrop-blur-sm">
            {categoryLabel(item)}
          </span>
        </div>
        {user && (
          <div className="absolute right-4 top-4 z-10 flex items-center gap-2">
            <ShareButton itemId={item.id} compact />
            <button
              type="button"
              onClick={() => toggleSave(item.id)}
              aria-label={saved ? "Remove from saved" : "Save"}
              aria-pressed={saved}
              className="grid h-10 w-10 place-items-center rounded-full border border-white/25 bg-black/40 text-xl backdrop-blur-sm transition-transform hover:scale-110 active:scale-90"
            >
              <span className={saved ? "text-accent" : "text-fg"}>{saved ? "♥" : "♡"}</span>
            </button>
          </div>
        )}
      </div>

      {(when || price) && (
        <p className="mt-6 flex items-center gap-3 font-mono text-xs tracking-wide text-accent">
          {when && <span>{when}</span>}
          {price && (
            <span className="rounded-full bg-accent px-2.5 py-0.5 font-bold text-accent-ink">
              {price}
            </span>
          )}
        </p>
      )}

      <h1 className="mt-2 text-balance text-3xl font-black leading-tight tracking-tight sm:text-4xl">
        {item.name}
      </h1>

      {item.description && (
        <p className="mt-5 whitespace-pre-line text-base leading-relaxed text-fg/80">
          {item.description}
        </p>
      )}

      {item.source_url && (
        <a
          href={item.source_url}
          target="_blank"
          rel="noreferrer"
          className="mt-8 inline-block rounded-full bg-accent px-5 py-2.5 font-bold text-accent-ink transition-transform hover:scale-105 active:scale-95"
        >
          open on {item.source} ↗
        </a>
      )}
    </main>
  );
}

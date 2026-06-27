"use client";

import Link from "next/link";
import { useState } from "react";

import type { Card } from "@/lib/api";
import { ShareButton } from "@/components/ShareButton";
import { useUser } from "@/components/UserContext";
import { categoryLabel, fallbackHue, formatPrice, formatWhen } from "@/lib/format";

export function EventCard({ card, index }: { card: Card; index: number }) {
  const when = formatWhen(card);
  const price = formatPrice(card);
  const hue = fallbackHue(card.id);
  const { user, savedIds, toggleSave } = useUser();
  const saved = savedIds.has(card.id);
  // Many image_urls point at arbitrary external hosts that 404 / block hotlinking;
  // fall back to the colored placeholder when the photo fails to load.
  const [imgError, setImgError] = useState(false);

  const inner = (
    <article
      className="rise group relative aspect-[3/4] overflow-hidden rounded-2xl border border-line bg-card"
      style={{ animationDelay: `${Math.min(index, 12) * 55}ms` }}
    >
      {/* Photo (plain <img> — sources are arbitrary external hosts). */}
      {card.image_url && !imgError ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={card.image_url}
          alt=""
          loading="lazy"
          onError={() => setImgError(true)}
          className="absolute inset-0 h-full w-full object-cover transition-transform duration-700 group-hover:scale-105"
        />
      ) : (
        <div
          className="absolute inset-0"
          style={{ background: `hsl(${hue} 55% 16%)` }}
        />
      )}

      <div className="scrim absolute inset-0" />

      {/* Accent hairline that grows on hover. */}
      <div className="absolute inset-x-0 bottom-0 h-[3px] origin-left scale-x-0 bg-accent transition-transform duration-300 group-hover:scale-x-100" />

      {/* Top-left: category. */}
      <div className="absolute inset-x-0 top-0 p-3.5">
        <span className="rounded-full border border-white/25 bg-black/30 px-2.5 py-1 font-mono text-[10px] font-medium tracking-[0.14em] text-fg backdrop-blur-sm">
          {categoryLabel(card)}
        </span>
      </div>

      {/* Bottom: when + price, name, blurb. */}
      <div className="absolute inset-x-0 bottom-0 p-4">
        {(when || price) && (
          <p className="mb-1.5 flex items-center gap-2 font-mono text-[11px] tracking-wide text-accent">
            {when && <span>{when}</span>}
            {price && (
              <span className="rounded-full bg-accent px-2 py-0.5 font-bold text-accent-ink">
                {price}
              </span>
            )}
          </p>
        )}
        <h3 className="text-balance text-xl font-extrabold leading-tight tracking-tight text-fg">
          {card.name}
        </h3>
        {card.blurb && (
          <p className="mt-2 line-clamp-3 text-sm leading-snug text-fg/75">{card.blurb}</p>
        )}
        <span className="mt-3 inline-flex items-center gap-1 font-mono text-[11px] tracking-wide text-muted transition-colors group-hover:text-fg">
          {card.source} →
        </span>
      </div>
    </article>
  );

  return (
    <div className="relative">
      {/* Heart + share live outside the <a> (a button can't nest in an anchor). */}
      {user && (
        <div className="absolute right-3 top-3 z-10 flex items-center gap-2">
          <ShareButton itemId={card.id} compact />
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              toggleSave(card.id);
            }}
            aria-label={saved ? "Remove from saved" : "Save"}
            aria-pressed={saved}
            className="grid h-9 w-9 place-items-center rounded-full border border-white/25 bg-black/40 text-lg backdrop-blur-sm transition-transform hover:scale-110 active:scale-90"
          >
            <span className={saved ? "text-accent" : "text-fg"}>{saved ? "♥" : "♡"}</span>
          </button>
        </div>
      )}

      {/* The card opens our detail page; the link to the source lives there. */}
      <Link href={`/item/${card.id}`} className="block">
        {inner}
      </Link>
    </div>
  );
}

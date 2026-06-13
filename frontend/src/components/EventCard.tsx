import type { Card } from "@/lib/api";
import { categoryLabel, fallbackHue, formatPrice, formatWhen } from "@/lib/format";

export function EventCard({ card, index }: { card: Card; index: number }) {
  const when = formatWhen(card);
  const price = formatPrice(card);
  const hue = fallbackHue(card.id);

  const inner = (
    <article
      className="rise group relative aspect-[3/4] overflow-hidden rounded-2xl border border-line bg-card"
      style={{ animationDelay: `${Math.min(index, 12) * 55}ms` }}
    >
      {/* Photo (plain <img> — sources are arbitrary external hosts). */}
      {card.image_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={card.image_url}
          alt=""
          loading="lazy"
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

      {/* Top row: category + when/price badges. */}
      <div className="absolute inset-x-0 top-0 flex items-start justify-between p-3.5">
        <span className="rounded-full border border-white/25 bg-black/30 px-2.5 py-1 font-mono text-[10px] font-medium tracking-[0.14em] text-fg backdrop-blur-sm">
          {categoryLabel(card)}
        </span>
        {price && (
          <span className="rounded-full bg-accent px-2.5 py-1 font-mono text-[10px] font-bold tracking-wide text-accent-ink">
            {price}
          </span>
        )}
      </div>

      {/* Bottom: name, when, blurb. */}
      <div className="absolute inset-x-0 bottom-0 p-4">
        {when && (
          <p className="mb-1.5 font-mono text-[11px] tracking-wide text-accent">{when}</p>
        )}
        <h3 className="text-balance text-xl font-extrabold leading-tight tracking-tight text-fg">
          {card.name}
        </h3>
        {card.blurb && (
          <p className="mt-2 line-clamp-3 text-sm leading-snug text-fg/75">{card.blurb}</p>
        )}
        {card.source_url && (
          <span className="mt-3 inline-flex items-center gap-1 font-mono text-[11px] tracking-wide text-muted transition-colors group-hover:text-fg">
            {card.source} ↗
          </span>
        )}
      </div>
    </article>
  );

  if (!card.source_url) return inner;
  return (
    <a href={card.source_url} target="_blank" rel="noreferrer" className="block">
      {inner}
    </a>
  );
}

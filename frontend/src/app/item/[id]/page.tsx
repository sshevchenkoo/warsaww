import type { Metadata } from "next";
import Link from "next/link";

import { ItemActions } from "@/components/ItemActions";
import { ItemImage } from "@/components/ItemImage";
import type { Card } from "@/lib/api";
import { categoryLabel, fallbackHue, formatPrice, formatWhen } from "@/lib/format";

// Server-side fetch straight to the API. The browser client uses relative proxy
// paths (see lib/api.ts / next.config.ts), but on the server we call the API
// directly so the page HTML is rendered on the server — SSR for a fast first
// paint and real SEO (title/description in the initial markup, not after hydration).
const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

async function fetchItem(id: string): Promise<Card | null> {
  const res = await fetch(`${BACKEND}/items/${id}`, { next: { revalidate: 60 } });
  return res.ok ? ((await res.json()) as Card) : null;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const item = await fetchItem(id);
  if (!item) return { title: "Not found · Warsaw" };
  const description = item.description?.slice(0, 160) ?? `${categoryLabel(item)} in Warsaw`;
  return { title: `${item.name} · Warsaw`, description };
}

export default async function ItemPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const item = await fetchItem(id);

  if (!item) {
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

  return (
    <main className="mx-auto w-full max-w-3xl px-5 pb-24 pt-8">
      <Link
        href="/"
        className="font-mono text-xs tracking-wide text-muted transition-colors hover:text-fg"
      >
        ← back
      </Link>

      <div className="relative mt-5 aspect-[16/9] overflow-hidden rounded-2xl border border-line bg-card">
        <ItemImage imageUrl={item.image_url} hue={hue} />
        <div className="absolute left-0 top-0 p-4">
          <span className="rounded-full border border-white/25 bg-black/30 px-2.5 py-1 font-mono text-[10px] font-medium tracking-[0.14em] text-fg backdrop-blur-sm">
            {categoryLabel(item)}
          </span>
        </div>
        <ItemActions itemId={item.id} />
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

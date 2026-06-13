import type { Card } from "./api";

const WHEN_FMT = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatWhen(card: Card): string {
  if (card.starts_at) return WHEN_FMT.format(new Date(card.starts_at));
  if (card.is_permanent) return "Open year-round";
  return "";
}

export function formatPrice(card: Card): string | null {
  if (card.price_from === 0) return "Free";
  if (card.price_from != null) return `from ${card.price_from} zł`;
  return null;
}

export function categoryLabel(card: Card): string {
  return (card.category ?? card.kind).toUpperCase();
}

// Deterministic accent tint for cards without a photo.
export function fallbackHue(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) % 360;
  return h;
}
